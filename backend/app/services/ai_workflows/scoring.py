# =============================================================================
# FGA CRM - Workflow IA 1 : Lead Scoring des deals
# =============================================================================
"""Score un deal (0-100, tier A/B/C) en croisant trois familles de signaux,
TOUTES deja presentes en base CRM (aucun appel externe autre que le LLM) :
- FIT ICP    : company (secteur, taille, levee, provenance)
- INTENT     : historique d'activites recentes (deal + contact)
- MESSAGE    : score d'audit Startup Radar (bas = opportunite haute)

Le resultat est persiste sur le deal (colonnes ai_*) avec model/prompt_version
(auditabilite), et chaque appel est trace dans ai_workflow_runs. Regle centrale :
rien d'inventable — tout signal absent va dans missing_signals."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.schemas.ai_workflows import SCORING_PROMPT_VERSION, DealScoreOutput
from app.services.ai_workflows.client import AiWorkflowError, call_openai_structured
from app.services.ai_workflows.runs import record_run

logger = logging.getLogger(__name__)

_MAX_ACTIVITIES = 20
_MAX_TEXT = 300  # borne des textes libres injectes dans le contexte (DC1)

SCORING_SYSTEM_PROMPT = """\
Tu es le moteur de scoring de FGA CRM. Ta mission : evaluer le potentiel
commercial d'un deal pour Fast Growth Advisors.

Contexte metier : FGA vend des audits de clarte du message (999 EUR, produit
"audit-999"), un accompagnement fondateur (499 EUR, produit "founder-499") et
de l'advisory (30-150K EUR, produit "advisory") a des startups B2B francaises,
prioritairement post-levee Seed/Serie A/B.

Modele de scoring (0-100) :
- FIT (0-50) : startup B2B francaise post-levee = fort ; SaaS/tech = fort ;
  effectif 10-100 = fort ; hors ICP = faible.
- INTENT (0-30) : activites recentes (reponse email, call, meeting) ; la
  recence pondere (une activite de cette semaine vaut plus qu'une d'il y a
  2 mois).
- OPPORTUNITE MESSAGE (0-20) : score d'audit Startup Radar BAS (sur 75) =
  opportunite HAUTE (le probleme de clarte existe et est mesure). Absence
  d'audit = 0 point et signale dans missing_signals.

Tiers : A si score >= 70, B si score >= 40, C sinon.

Regles absolues :
- N'invente AUCUN signal. Chaque point attribue doit etre tracable a une
  donnee fournie dans le contexte.
- Tout signal absent va dans missing_signals ; il ne penalise pas mais ne
  rapporte aucun point.
- rationale : 2-3 phrases en francais, factuel, sans superlatifs.
- recommended_product : le produit FGA le plus adapte au vu des signaux,
  ou null si indeterminable.
"""


def _clip(value: object) -> str | None:
    if value is None:
        return None
    return str(value)[:_MAX_TEXT]


async def _collect_signals(db: AsyncSession, deal: Deal) -> dict:
    """Assemble le contexte de scoring depuis la base (deal + company + contact
    + activites recentes). Aucune donnee inventee : les champs absents sont None."""
    company: Company | None = (
        await db.get(Company, deal.company_id) if deal.company_id else None
    )
    contact: Contact | None = (
        await db.get(Contact, deal.contact_id) if deal.contact_id else None
    )

    # Flags/score d'audit SR : champs DERIVES des activites d'audit (pas des
    # colonnes Company). Reutilise le helper des routes companies (DC8) —
    # import tardif pour eviter tout cycle route <-> service.
    audit_flags: dict = {}
    audit_score: int | None = None
    if company is not None:
        from app.api.v1.companies import _fetch_audit_flags

        audit_map, score_map = await _fetch_audit_flags(db, [company.id])
        audit_flags = audit_map.get(company.id, {})
        audit_score = score_map.get(company.id)

    # Activites recentes liees au deal ou au contact (intent).
    activity_filters = []
    if deal.id is not None:
        activity_filters.append(Activity.deal_id == deal.id)
    if deal.contact_id is not None:
        activity_filters.append(Activity.contact_id == deal.contact_id)
    activities: list[Activity] = []
    if activity_filters:
        activities = (
            (
                await db.execute(
                    select(Activity)
                    .where(or_(*activity_filters))
                    .order_by(Activity.created_at.desc())
                    .limit(_MAX_ACTIVITIES)
                )
            )
            .scalars()
            .all()
        )

    return {
        "deal": {
            "title": _clip(deal.title),
            "stage": deal.stage,
            "amount_eur": deal.amount,
            "product": deal.product,
            "pricing_type": deal.pricing_type,
            "priority": deal.priority,
            "created_at": deal.created_at.isoformat() if deal.created_at else None,
            "expected_close_date": (
                deal.expected_close_date.isoformat() if deal.expected_close_date else None
            ),
        },
        "company": None if company is None else {
            "name": _clip(company.name),
            "industry": _clip(company.industry),
            "size_range": company.size_range,
            "country": _clip(company.country),
            "lead_source": company.lead_source,
            "audit_score_sur_75": audit_score,
            "has_audit_messaging": audit_flags.get("has_messaging", False),
            "has_audit_detailed": audit_flags.get("has_detailed", False),
            "has_audit_geo": audit_flags.get("has_geo", False),
            "funding_date": (
                company.funding_date.isoformat() if company.funding_date else None
            ),
            "funding_amount_eur": company.funding_amount,
            "funding_series": company.funding_series,
            "description": _clip(company.description),
        },
        "contact": None if contact is None else {
            "title": _clip(contact.title),
            "is_decision_maker": contact.is_decision_maker,
            "email_status": contact.email_status,
        },
        "recent_activities": [
            {
                "type": a.type,
                "subject": _clip(a.subject),
                "date": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activities
        ],
        "date_du_jour": datetime.now(UTC).date().isoformat(),
    }


async def score_deal(db: AsyncSession, deal: Deal) -> DealScoreOutput:
    """Score un deal : signaux -> LLM -> validation -> persistance colonnes ai_*.

    Trace le run (ok / parse_error / api_error) dans ai_workflow_runs. En cas
    d'echec LLM, le deal n'est PAS modifie et AiWorkflowError est propagee
    (l'appelant decide du code HTTP). Commit gere ici (resultat + run ensemble).
    """
    signals = await _collect_signals(db, deal)
    user_content = json.dumps(signals, ensure_ascii=False)

    try:
        output, usage = await call_openai_structured(
            DealScoreOutput,
            system=SCORING_SYSTEM_PROMPT,
            user=user_content,
            name="deal_score",
        )
    except AiWorkflowError as exc:
        record_run(
            db, organization_id=deal.organization_id, workflow="scoring",
            target_type="deal", target_id=deal.id,
            prompt_version=SCORING_PROMPT_VERSION, model=settings.ai_workflows_model,
            status=exc.kind, error=str(exc),
        )
        await db.commit()  # le run d'echec est trace meme sans resultat
        raise

    deal.ai_score = output.score
    deal.ai_tier = output.tier
    deal.ai_score_rationale = output.rationale
    deal.ai_score_missing = list(output.missing_signals)
    deal.ai_scored_at = datetime.now(UTC)
    deal.ai_score_meta = {
        "model": settings.ai_workflows_model,
        "prompt_version": SCORING_PROMPT_VERSION,
        "recommended_product": output.recommended_product,
        "fit_points": output.fit_points,
        "intent_points": output.intent_points,
        "message_points": output.message_points,
    }
    record_run(
        db, organization_id=deal.organization_id, workflow="scoring",
        target_type="deal", target_id=deal.id,
        prompt_version=SCORING_PROMPT_VERSION, model=settings.ai_workflows_model,
        status="ok", input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
    )
    await db.commit()
    await db.refresh(deal)
    return output
