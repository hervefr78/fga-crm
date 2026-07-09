# =============================================================================
# FGA CRM - Workflow IA 4 : draft d'outreach contextualise (Lead Engine)
# =============================================================================
"""Genere un draft d'email d'outreach a partir d'un signal mmf_gap
(docs/LEAD_ENGINE_VISION.md §4.2 rajout 4).

Regle metier (memoire mmf-driver-principle) : l'angle du message est TOUJOURS
le MMF gap mesure (audit SR /75) — c'est le probleme que FGA vend. La levee de
fonds n'apparait que comme qualificateur d'urgence (« c'est maintenant que
votre message doit porter »), jamais comme motif du contact.

Garde-fou non negociable (§2.4) : ce draft n'est JAMAIS envoye automatiquement.
Il est stocke sur le signal et passe par la validation humaine (composer email).
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead_engine import LeadSignal
from app.models.user import User
from app.schemas.ai_workflows import OUTREACH_PROMPT_VERSION, OutreachDraftOutput
from app.services.ai_workflows.client import AiWorkflowError, call_openai_structured
from app.services.ai_workflows.runs import record_run

logger = logging.getLogger(__name__)

OUTREACH_SYSTEM_PROMPT = """\
Tu rediges des emails d'outreach pour Fast Growth Advisors (FGA), cabinet
d'advisory premium pour startups B2B francaises. FGA vend la resolution du
Message-Market Fit gap : la clarte du message mesuree par un audit (score /75).

Regle d'or (a ne JAMAIS inverser) :
- L'ANGLE du message est le MMF gap mesure : « votre clarte de message est
  mesuree a X/75 — voici ce que ca coute en pipeline/conversion ».
- La levee de fonds n'est QU'UN qualificateur d'urgence : si des fonds recents
  existent, conclure sur « c'est maintenant que votre message doit porter ».
  Ne JAMAIS ouvrir sur la levee, ne jamais feliciter pour la levee.

Contraintes de redaction :
- Francais, tutoiement interdit (vouvoyer). 90-140 mots maximum dans le corps.
- Factuel et specifique : citer le score mesure. AUCUN chiffre invente,
  aucune promesse chiffree. Pas de superlatifs, pas de jargon marketing.
- Transparence RGPD : une ligne indiquant la source du contact (interet
  legitime B2B), ex. « Je vous ecris car [source fournie dans le contexte] ».
- Terminer par une question simple (proposition d'echange de 15-20 min),
  pas de lien de booking, pas de pression.
- Signature : uniquement le prenom/nom fournis dans le contexte (pas de titre
  invente).
- subject : 6-10 mots, specifique, sans majuscules criardes ni emoji.
- personalization_used : lister les donnees du contexte reellement utilisees.
"""


def _clip(value: object, limit: int = 300) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _build_user_prompt(
    signal: LeadSignal, company: Company | None, contact: Contact, sender: User
) -> str:
    """Contexte 100 % factuel (DC3 : rien d'inventable par le LLM)."""
    payload = signal.payload_json or {}
    lines = [
        "## Cible",
        f"- Contact : {contact.full_name}"
        + (f", {contact.title}" if contact.title else ""),
        f"- Societe : {payload.get('company_name') or (company.name if company else 'inconnue')}",
    ]
    if company and company.industry:
        lines.append(f"- Secteur : {_clip(company.industry)}")

    lines.append("\n## Signal mesure (l'angle du message)")
    score = payload.get("audit_score")
    lines.append(
        f"- Audit de clarte du message : {score}/75" if score is not None
        else "- Audit de clarte du message : sous le seuil (score exact non fourni)"
    )

    lines.append("\n## Qualificateur solvabilite (jamais l'angle)")
    if payload.get("funding_date"):
        amount = payload.get("funding_amount")
        lines.append(
            f"- Levee : {payload.get('funding_date')}"
            + (f", {amount} EUR" if amount else ", montant inconnu")
            + (f" ({payload.get('funding_series')})" if payload.get("funding_series") else "")
        )
    else:
        lines.append("- Aucune levee recente connue : ne pas evoquer de fonds.")

    lines += [
        "\n## Source du contact (transparence RGPD)",
        "- Veille FGA sur les startups B2B francaises (donnees publiques "
        "d'entreprises et audit public de votre communication).",
        "\n## Expediteur",
        f"- {sender.full_name} — Fast Growth Advisors",
    ]
    return "\n".join(lines)


async def generate_outreach_draft(
    db: AsyncSession,
    signal: LeadSignal,
    contact: Contact,
    user: User,
) -> tuple[OutreachDraftOutput, dict]:
    """Appelle le LLM et trace le run. Ne PERSISTE PAS le draft (caller).

    Leve AiWorkflowError (api_error | parse_error) en cas d'echec — le signal
    reste intact et le run d'echec est trace.
    """
    company = None
    if signal.company_id is not None:
        company = await db.get(Company, signal.company_id)

    user_prompt = _build_user_prompt(signal, company, contact, user)
    try:
        output, usage = await call_openai_structured(
            OutreachDraftOutput,
            system=OUTREACH_SYSTEM_PROMPT,
            user=user_prompt,
            name="outreach_draft",
        )
    except AiWorkflowError as exc:
        record_run(
            db, organization_id=user.organization_id, workflow="outreach",
            target_type="signal", target_id=signal.id,
            prompt_version=OUTREACH_PROMPT_VERSION, model=settings.ai_workflows_model,
            status=exc.kind, error=str(exc),
        )
        await db.commit()
        raise

    record_run(
        db, organization_id=user.organization_id, workflow="outreach",
        target_type="signal", target_id=signal.id,
        prompt_version=OUTREACH_PROMPT_VERSION, model=settings.ai_workflows_model,
        status="ok",
        input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
    )
    meta = {
        "model": settings.ai_workflows_model,
        "prompt_version": OUTREACH_PROMPT_VERSION,
    }
    return output, meta
