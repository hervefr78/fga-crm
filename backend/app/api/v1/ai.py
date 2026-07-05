# =============================================================================
# FGA CRM - AI Next-Action Routes (mock simple, pas de LLM)
# =============================================================================

# Suggestions deterministes basees sur les attributs de l'entite (Company /
# Contact / Deal). Aucun appel externe, aucune ecriture en base. Cote frontend,
# le composant "AI card" affiche `title` + `body` et les CTA si presents.

import contextlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import check_entity_access, check_tenant_access
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User
from app.schemas.ai import NextActionAction, NextActionResponse

router = APIRouter()

# Constantes (DC8 — source unique pour la logique mock)
STALE_CONTACT_DAYS = 30  # > 30 jours sans activite => "Relancer"
DEAL_CLOSE_URGENCY_DAYS = 7  # < 7 jours avant cloture => "Relance urgente"
LOW_AUDIT_SCORE_THRESHOLD = 50  # score < 50 => "Identifier les leviers"


# ---------------------------------------------------------------------------
# Helpers — recuperation des entites avec verification RBAC
# ---------------------------------------------------------------------------


async def _get_company_or_404(
    db: AsyncSession, company_id: uuid.UUID, user: User
) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise non trouvee")
    check_tenant_access(company, user)  # isolation multi-tenant AVANT ownership
    check_entity_access(company, user)
    return company


async def _get_contact_or_404(
    db: AsyncSession, contact_id: uuid.UUID, user: User
) -> Contact:
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouve")
    check_tenant_access(contact, user)  # isolation multi-tenant AVANT ownership
    check_entity_access(contact, user)
    return contact


async def _get_deal_or_404(
    db: AsyncSession, deal_id: uuid.UUID, user: User
) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_tenant_access(deal, user)  # isolation multi-tenant AVANT ownership
    check_entity_access(deal, user)
    return deal


# ---------------------------------------------------------------------------
# Helpers — derivations metier
# ---------------------------------------------------------------------------


async def _company_audit_summary(
    db: AsyncSession, company_id: uuid.UUID
) -> tuple[bool, int | None]:
    """Retourner (has_audit, best_score) pour une company.

    Reproduit la logique de `companies.list_companies` mais limitee a une
    seule company. Le score "detailed" (/75) prime sur "messaging" (/10).
    """
    audit_query = (
        select(
            cast(Activity.metadata_["audit_type"], String).label("audit_type"),
            cast(Activity.metadata_["total_score"], String).label("total_score"),
            cast(Activity.metadata_["messaging_score"], String).label("messaging_score"),
        )
        .where(
            Activity.company_id == company_id,
            Activity.type == "audit",
            Activity.metadata_["audit_type"] != None,  # noqa: E711
        )
        .limit(50)  # DC1 — borne defensive
    )
    rows = (await db.execute(audit_query)).all()

    if not rows:
        return (False, None)

    best_score: int | None = None
    for row in rows:
        if row.audit_type == "detailed" and row.total_score:
            with contextlib.suppress(ValueError, TypeError):
                v = int(float(row.total_score))
                if best_score is None or v > best_score:
                    best_score = v
        elif row.audit_type == "messaging" and row.messaging_score and best_score is None:
            with contextlib.suppress(ValueError, TypeError):
                best_score = int(float(row.messaging_score))

    return (True, best_score)


async def _contact_last_activity_at(
    db: AsyncSession, contact_id: uuid.UUID
) -> datetime | None:
    """Date de la derniere activite liee au contact (None si aucune)."""
    result = await db.execute(
        select(func.max(Activity.created_at)).where(Activity.contact_id == contact_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Endpoint Company — /api/v1/companies/{company_id}/next-action
# ---------------------------------------------------------------------------


@router.get(
    "/companies/{company_id}/next-action",
    response_model=NextActionResponse,
)
async def company_next_action(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NextActionResponse:
    """Suggestion d'action sur une Company (regles simples sur audit_score)."""
    company = await _get_company_or_404(db, company_id, user)
    has_audit, score = await _company_audit_summary(db, company.id)

    if not has_audit:
        return NextActionResponse(
            title="Lancer un audit Startup Radar",
            body=(
                f"Aucun audit n'a encore ete realise pour {company.name}. Lance"
                " un audit pour identifier les leviers d'amelioration."
            ),
            primary_action=NextActionAction(label="Voir les audits", type="view"),
        )

    if score is not None and score < LOW_AUDIT_SCORE_THRESHOLD:
        return NextActionResponse(
            title="Identifier les leviers d'amelioration",
            body=(
                f"L'audit de {company.name} a un score de {score}. Concentre-toi"
                " sur les axes a fort potentiel pour relancer la conversation."
            ),
            primary_action=NextActionAction(label="Voir l'audit", type="view"),
            secondary_action=NextActionAction(label="Creer une tache", type="create_task"),
        )

    return NextActionResponse(
        title="Identifier un decideur dans cette entreprise",
        body=(
            f"L'audit de {company.name} est solide. Prochaine etape : trouver"
            " un decideur clef et engager le contact."
        ),
        primary_action=NextActionAction(label="Voir les contacts", type="view"),
    )


# ---------------------------------------------------------------------------
# Endpoint Contact — /api/v1/contacts/{contact_id}/next-action
# ---------------------------------------------------------------------------


@router.get(
    "/contacts/{contact_id}/next-action",
    response_model=NextActionResponse,
)
async def contact_next_action(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NextActionResponse:
    """Suggestion d'action sur un Contact (regles last_activity / email / status)."""
    contact = await _get_contact_or_404(db, contact_id, user)

    # Pas d'email = priorite absolue (impossible de faire quoi que ce soit sans)
    if not contact.email:
        return NextActionResponse(
            title="Trouver l'email de ce contact",
            body=(
                f"Aucun email connu pour {contact.full_name}. Lance la recherche"
                " automatique (Icypeas) pour tenter de le trouver."
            ),
            primary_action=NextActionAction(label="Trouver l'email", type="find_email"),
        )

    # Stale : pas d'activite depuis plus de 30 jours.
    # Normaliser naive/aware avant comparaison : SQLite renvoie naive,
    # PostgreSQL renvoie aware. On force aware-UTC pour les naive.
    last_activity = await _contact_last_activity_at(db, contact.id)
    last_seen = last_activity or contact.last_contacted_at
    is_stale = False
    if last_seen is not None:
        last_seen_aware = (
            last_seen if last_seen.tzinfo is not None else last_seen.replace(tzinfo=UTC)
        )
        threshold = datetime.now(UTC) - timedelta(days=STALE_CONTACT_DAYS)
        is_stale = last_seen_aware < threshold

    if is_stale:
        return NextActionResponse(
            title="Relancer ce contact",
            body=(
                f"Aucune activite avec {contact.full_name} depuis plus de"
                f" {STALE_CONTACT_DAYS} jours. Une relance ciblee peut redemarrer"
                " la conversation."
            ),
            primary_action=NextActionAction(label="Composer un email", type="compose_email"),
            secondary_action=NextActionAction(label="Reporter", type="snooze"),
        )

    # Decideur identifie + statut new = candidat ideal pour prospection
    if contact.is_decision_maker and contact.status == "new":
        return NextActionResponse(
            title="Envoyer un email de prospection ciblee",
            body=(
                f"{contact.full_name} est un decideur identifie au statut 'new'."
                " Envoie un email d'introduction personnalise pour engager."
            ),
            primary_action=NextActionAction(label="Composer un email", type="compose_email"),
            secondary_action=NextActionAction(label="Creer une tache", type="create_task"),
        )

    # Defaut : suivi standard
    return NextActionResponse(
        title="Planifier un suivi",
        body=(
            f"Maintiens la relation avec {contact.full_name} en planifiant la"
            " prochaine action (call, meeting, email)."
        ),
        primary_action=NextActionAction(label="Creer une tache", type="create_task"),
    )


# ---------------------------------------------------------------------------
# Endpoint Deal — /api/v1/deals/{deal_id}/next-action
# ---------------------------------------------------------------------------


# Mapping stage -> suggestion par defaut (DC8 — DC5 etats exhaustifs)
DEAL_STAGE_SUGGESTIONS: dict[str, tuple[str, str, str]] = {
    "new": (
        "Premier contact",
        "Engage le premier contact pour qualifier le deal et avancer dans le pipeline.",
        "compose_email",
    ),
    "contacted": (
        "Programmer un call decouverte",
        "Le contact est etabli. Programme un call decouverte pour qualifier le besoin.",
        "create_task",
    ),
    "meeting": (
        "Envoyer la proposition",
        "Le meeting decouverte a eu lieu. Prepare et envoie la proposition commerciale.",
        "compose_email",
    ),
    "proposal": (
        "Suivre la proposition",
        "La proposition a ete envoyee. Relance le contact pour avoir un retour.",
        "compose_email",
    ),
    "negotiation": (
        "Lever les dernieres objections",
        "La negociation est en cours. Identifie et adresse les dernieres objections pour signer.",
        "create_task",
    ),
}


@router.get("/deals/{deal_id}/next-action")
async def deal_next_action(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Suggestion d'action sur un Deal selon stage et expected_close_date.

    Cas particulier : stage='lost' => 204 No Content (aucune suggestion utile).
    """
    deal = await _get_deal_or_404(db, deal_id, user)

    # Deal perdu : pas de suggestion (le frontend masque l'AI card sur 204)
    if deal.stage == "lost":
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Deal gagne : onboarding
    if deal.stage == "won":
        payload = NextActionResponse(
            title="Demarrer l'onboarding",
            body=(
                f"Le deal '{deal.title}' est signe. Lance l'onboarding client"
                " pour assurer une bonne premiere experience."
            ),
            primary_action=NextActionAction(label="Creer une tache", type="create_task"),
        )
        return Response(
            content=payload.model_dump_json(),
            media_type="application/json",
        )

    # Pipeline + cloture imminente : urgence (DC1 — borne sur expected_close_date)
    if (
        deal.stage in ("proposal", "negotiation")
        and deal.expected_close_date is not None
    ):
        from datetime import date as _date

        days_left = (deal.expected_close_date - _date.today()).days
        if 0 <= days_left < DEAL_CLOSE_URGENCY_DAYS:
            payload = NextActionResponse(
                title="Relance urgente avant cloture",
                body=(
                    f"Le deal '{deal.title}' est cense se cloturer dans"
                    f" {days_left} jour(s). Relance immediate recommandee."
                ),
                primary_action=NextActionAction(label="Composer un email", type="compose_email"),
                secondary_action=NextActionAction(label="Creer une tache", type="create_task"),
            )
            return Response(
                content=payload.model_dump_json(),
                media_type="application/json",
            )

    # Pipeline standard : suggestion par stage (DC5 — exhaustif sur DEAL_STAGE_SUGGESTIONS)
    suggestion = DEAL_STAGE_SUGGESTIONS.get(deal.stage)
    if suggestion is None:
        # Garde defensif (DC2 — pas de fallback silencieux mensonger)
        # Stage inconnu : on retourne quand meme une suggestion neutre.
        payload = NextActionResponse(
            title="Avancer le deal",
            body=f"Identifie la prochaine etape pour avancer le deal '{deal.title}'.",
            primary_action=NextActionAction(label="Creer une tache", type="create_task"),
        )
    else:
        title, body, action_type = suggestion
        payload = NextActionResponse(
            title=title,
            body=f"{body} (Deal : '{deal.title}')",
            primary_action=NextActionAction(
                label=("Composer un email" if action_type == "compose_email" else "Creer une tache"),
                type=action_type,
            ),
        )

    return Response(
        content=payload.model_dump_json(),
        media_type="application/json",
    )
