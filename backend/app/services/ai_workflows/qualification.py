# =============================================================================
# FGA CRM - Workflow IA 2 : Qualification SPICED des contacts inbound
# =============================================================================
"""Applique le framework SPICED de facon identique a chaque contact (inbound
formulaire, telechargement Observatoire, import...) et recommande un routage :
fast_track | standard | human_review. Regle non negociable : JAMAIS de
disqualification automatique — human_review est une revue humaine, pas une
poubelle.

fast_track : un deal est cree automatiquement (stage 'new' — les stages reels
FGA n'ont pas 'qualified') avec le produit suggere, owner = le user declencheur.

Chaque champ SPICED rempli doit etre tracable a une donnee fournie ; sinon
'unknown'. Resultat persiste sur le contact (ai_qualification / ai_routing /
ai_qualified_at) + run trace dans ai_workflow_runs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User
from app.schemas.ai_workflows import QUALIF_PROMPT_VERSION, ContactQualifyOutput
from app.services.ai_workflows.client import AiWorkflowError, call_openai_structured
from app.services.ai_workflows.runs import record_run

logger = logging.getLogger(__name__)

_MAX_ACTIVITIES = 20
_MAX_TEXT = 300

QUALIF_SYSTEM_PROMPT = """\
Tu es le moteur de qualification inbound de FGA CRM.

Contexte metier : Fast Growth Advisors vend des audits de clarte du message
(999 EUR, "audit-999"), un accompagnement fondateur (499 EUR, "founder-499")
et de l'advisory (30-150K EUR, "advisory") a des startups B2B francaises.

Framework SPICED. Pour chaque dimension, remplis "value" uniquement si
l'information est presente dans les donnees fournies, sinon "unknown"
(et source = "unknown") :
- situation : contexte entreprise (taille, stade, levee)
- pain : douleur exprimee ou deductible d'un fait fourni (ex. telechargement
  de l'Observatoire = interet pour la clarte du message, PAS une douleur
  confirmee : le noter comme signal, pas comme pain etabli)
- impact : consequence business de la douleur si exprimee
- critical_event : echeance (levee en cours, lancement produit)
- decision : role du contact dans la decision (titre, mandat)

Routage :
- fast_track : pain ou critical_event explicite + contact decisionnaire + fit ICP
- standard : fit ICP probable mais dimensions cles unknown
- human_review : signaux contradictoires, hors ICP apparent, ou donnees
  insuffisantes. JAMAIS de disqualification.

Regles absolues :
- Chaque champ rempli doit etre tracable a une donnee fournie ("source" cite
  la donnee). Ne deduis pas un budget d'une taille d'entreprise. Ne deduis pas
  une autorite d'un prenom.
- next_action : 1 phrase actionnable en francais pour le commercial.
- routing_rationale : 1-2 phrases factuelles.
"""


def _clip(value: object) -> str | None:
    if value is None:
        return None
    return str(value)[:_MAX_TEXT]


async def _collect_signals(
    db: AsyncSession, contact: Contact, submission_text: str | None
) -> dict:
    """Contexte de qualification : contact + entreprise + activites + soumission."""
    company: Company | None = (
        await db.get(Company, contact.company_id) if contact.company_id else None
    )
    activities = (
        (
            await db.execute(
                select(Activity)
                .where(Activity.contact_id == contact.id)
                .order_by(Activity.created_at.desc())
                .limit(_MAX_ACTIVITIES)
            )
        )
        .scalars()
        .all()
    )

    return {
        "contact": {
            "title": _clip(contact.title),
            "job_level": contact.job_level,
            "department": _clip(contact.department),
            "is_decision_maker": contact.is_decision_maker,
            "status": contact.status,
            "source": _clip(contact.source),
            "tags": list(contact.tags or [])[:10],
            "email_status": contact.email_status,
            "last_contacted_at": (
                contact.last_contacted_at.isoformat() if contact.last_contacted_at else None
            ),
        },
        "company": None if company is None else {
            "name": _clip(company.name),
            "industry": _clip(company.industry),
            "size_range": company.size_range,
            "country": _clip(company.country),
            "lead_source": company.lead_source,
            "funding_date": (
                company.funding_date.isoformat() if company.funding_date else None
            ),
            "funding_amount_eur": company.funding_amount,
            "funding_series": company.funding_series,
            "description": _clip(company.description),
        },
        "recent_activities": [
            {
                "type": a.type,
                "subject": _clip(a.subject),
                "date": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activities
        ],
        "submission_text": submission_text,
        "date_du_jour": datetime.now(UTC).date().isoformat(),
    }


def _fast_track_deal(contact: Contact, company: Company | None, user: User, output: ContactQualifyOutput) -> Deal:
    """Deal cree automatiquement sur fast_track (stage reel 'new')."""
    who = f"{contact.first_name} {contact.last_name}".strip()
    title = f"{company.name if company else who} — inbound qualifie"
    return Deal(
        title=title[:255],
        stage="new",
        product=output.suggested_product,
        contact_id=contact.id,
        company_id=contact.company_id,
        owner_id=user.id,
        organization_id=contact.organization_id,
        description=f"Deal cree automatiquement (qualification IA fast_track). {output.routing_rationale}"[:5000],
    )


async def qualify_contact(
    db: AsyncSession, contact: Contact, user: User, submission_text: str | None = None
) -> tuple[ContactQualifyOutput, Deal | None]:
    """Qualifie un contact : signaux -> LLM -> persistance + deal auto si fast_track.

    En cas d'echec LLM : contact intact, run d'echec trace, AiWorkflowError propagee.
    """
    signals = await _collect_signals(db, contact, submission_text)
    user_content = json.dumps(signals, ensure_ascii=False)

    try:
        output, usage = await call_openai_structured(
            ContactQualifyOutput,
            system=QUALIF_SYSTEM_PROMPT,
            user=user_content,
            name="contact_qualification",
        )
    except AiWorkflowError as exc:
        record_run(
            db, organization_id=contact.organization_id, workflow="qualification",
            target_type="contact", target_id=contact.id,
            prompt_version=QUALIF_PROMPT_VERSION, model=settings.ai_workflows_model,
            status=exc.kind, error=str(exc),
        )
        await db.commit()
        raise

    contact.ai_qualification = {
        "spiced": output.spiced.model_dump(),
        "routing_rationale": output.routing_rationale,
        "suggested_product": output.suggested_product,
        "next_action": output.next_action,
        "model": settings.ai_workflows_model,
        "prompt_version": QUALIF_PROMPT_VERSION,
    }
    contact.ai_routing = output.routing
    contact.ai_qualified_at = datetime.now(UTC)

    deal: Deal | None = None
    if output.routing == "fast_track":
        company = (
            await db.get(Company, contact.company_id) if contact.company_id else None
        )
        deal = _fast_track_deal(contact, company, user, output)
        db.add(deal)

    record_run(
        db, organization_id=contact.organization_id, workflow="qualification",
        target_type="contact", target_id=contact.id,
        prompt_version=QUALIF_PROMPT_VERSION, model=settings.ai_workflows_model,
        status="ok", input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
    )
    await db.commit()
    await db.refresh(contact)
    if deal is not None:
        await db.refresh(deal)
    return output, deal
