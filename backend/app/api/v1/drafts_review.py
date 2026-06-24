# =============================================================================
# FGA CRM - Drafts Review (proxy securise vers compass-core)
# =============================================================================
# Le frontend relit les drafts compass-core via ce proxy. La cle service
# compass-core reste cote serveur (jamais exposee au navigateur). Chaque route
# est protegee par l'auth utilisateur du CRM (get_current_user).

import csv
import io
import logging
import uuid
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.contact import Contact
from app.models.user import User
from app.schemas.draft_review import Brand, DraftReview, DraftStatusUpdateIn
from app.services.compass import (
    CompassClient,
    CompassNotConfiguredError,
    CompassNotFoundError,
    CompassServiceError,
    get_compass_client,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Marques autorisees pour le filtre `brand` (miroir compass-core).
ALLOWED_BRANDS: frozenset[str] = frozenset({"fga", "nomo", "ppd"})

# Bornes de `max_age_hours` (miroir compass-core : ge=1, le=720, default=48).
MAX_AGE_HOURS_DEFAULT = 48
MAX_AGE_HOURS_MIN = 1
MAX_AGE_HOURS_MAX = 720

# Cap du nombre de drafts approuves tires de compass-core pour l'export
# (miroir compass-core : limit le=1000). On prend le maximum autorise.
EXPORT_DRAFTS_LIMIT = 1000

# Types de drafts compass-core mappes sur les colonnes HeyReach (miroir
# compass-core DraftType : linkedin_invitation | linkedin_dm | linkedin_relance).
DRAFT_TYPE_INVITATION = "linkedin_invitation"
DRAFT_TYPE_DM = "linkedin_dm"
DRAFT_TYPE_RELANCE = "linkedin_relance"

# Entete CSV HeyReach — ordre et noms exacts attendus par l'import.
HEYREACH_CSV_HEADER = [
    "first_name",
    "last_name",
    "linkedin_url",
    "company",
    "brand",
    "invitation",
    "dm_followup",
    "final_relance",
]


def _raise_for_compass_error(exc: Exception) -> NoReturn:
    """Traduit une erreur du client compass-core en HTTPException (ne retourne JAMAIS).

    - not-configured -> 503
    - not-found       -> 404
    - service-error   -> 502

    Annote `NoReturn` pour que le type-checker sache que le flux ne continue pas
    apres le `except` (sinon `rows`/`row` apparaissent faussement non-lies).
    """
    if isinstance(exc, CompassNotConfiguredError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="compass not configured",
        )
    if isinstance(exc, CompassNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )
    if isinstance(exc, CompassServiceError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="compass service error",
        )
    raise exc  # erreur inattendue : laisser remonter


@router.get("/pending", response_model=list[DraftReview])
async def list_pending_drafts(
    brand: Brand | None = Query(default=None),
    max_age_hours: int = Query(
        default=MAX_AGE_HOURS_DEFAULT,
        ge=MAX_AGE_HOURS_MIN,
        le=MAX_AGE_HOURS_MAX,
    ),
    user: User = Depends(get_current_user),
    compass: CompassClient = Depends(get_compass_client),
) -> list[DraftReview]:
    """Liste les drafts a relire (proxy vers compass GET /v1/drafts/pending).

    `brand` est valide contre {fga, nomo, ppd} (Literal -> 422 si invalide).
    `max_age_hours` est borne (1..720). La pagination/le cap sont geres par
    compass-core.
    """
    # Defense en profondeur : meme si le Literal valide deja, on rejette toute
    # valeur hors liste autorisee (DC1).
    if brand is not None and brand not in ALLOWED_BRANDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid brand",
        )

    try:
        rows = await compass.list_pending_drafts(
            brand=brand, max_age_hours=max_age_hours
        )
    except (
        CompassNotConfiguredError,
        CompassNotFoundError,
        CompassServiceError,
    ) as exc:
        _raise_for_compass_error(exc)

    return [DraftReview.model_validate(row) for row in rows]


@router.get("/export.csv")
async def export_heyreach_csv(
    brand: Brand | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    compass: CompassClient = Depends(get_compass_client),
) -> Response:
    """Exporte les drafts APPROUVES en CSV pret a importer dans HeyReach.

    On tire les drafts `approved` de compass-core, on les groupe par `lead_id`
    (les 3 messages d'un lead partagent le meme lead_id), on pivote
    invitation/dm/relance en colonnes, puis on joint l'identite du contact CRM
    (first_name, last_name, linkedin_url, company). Une ligne n'est exportee
    que si le contact a une URL LinkedIn ET une invitation non vides (HeyReach
    exige les deux). `brand` filtre l'export et est forwarde a compass.
    """
    # Defense en profondeur : le Literal valide deja, on rejette tout hors liste.
    if brand is not None and brand not in ALLOWED_BRANDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid brand",
        )

    try:
        approved = await compass.list_drafts_by_status(
            status="approved", brand=brand, limit=EXPORT_DRAFTS_LIMIT
        )
    except (
        CompassNotConfiguredError,
        CompassNotFoundError,
        CompassServiceError,
    ) as exc:
        _raise_for_compass_error(exc)

    # 1) Grouper par lead_id et pivoter les 3 types en colonnes.
    #    `leads` : lead_id -> {invitation, dm_followup, final_relance, brand}.
    leads: dict[str, dict[str, str]] = {}
    for draft in approved:
        lead_id = draft.get("lead_id")
        if not lead_id:
            continue
        entry = leads.setdefault(
            lead_id,
            {"invitation": "", "dm_followup": "", "final_relance": "", "brand": ""},
        )
        # Le brand est le meme pour tous les drafts d'un lead ; on garde le dernier vu.
        if draft.get("brand"):
            entry["brand"] = draft["brand"]
        draft_type = draft.get("type")
        content = draft.get("content") or ""
        if draft_type == DRAFT_TYPE_INVITATION:
            entry["invitation"] = content
        elif draft_type == DRAFT_TYPE_DM:
            entry["dm_followup"] = content
        elif draft_type == DRAFT_TYPE_RELANCE:
            entry["final_relance"] = content

    # 2) Resoudre les lead_id en UUID (ignorer ceux qui ne sont pas des UUID).
    #    `uuid_to_lead` : UUID -> lead_id original (cle de `leads`).
    uuid_to_lead: dict[uuid.UUID, str] = {}
    for lead_id in leads:
        try:
            uuid_to_lead[uuid.UUID(lead_id)] = lead_id
        except (ValueError, AttributeError, TypeError):
            # lead_id non-UUID : pas de contact CRM joignable, on l'ignore.
            continue

    # 3) Charger les contacts en UNE requete (select minimal via relation ciblee).
    contacts_by_id: dict[uuid.UUID, Contact] = {}
    if uuid_to_lead:
        stmt = (
            select(Contact)
            .options(selectinload(Contact.company))
            .where(Contact.id.in_(list(uuid_to_lead.keys())))
        )
        result = await db.execute(stmt)
        for contact in result.scalars().all():
            contacts_by_id[contact.id] = contact

    # 4) Construire les lignes : une ligne uniquement si url + invitation non vides.
    rows_to_write: list[list[str]] = []
    skipped = 0
    for contact_uuid, lead_id in uuid_to_lead.items():
        lead = leads[lead_id]
        contact = contacts_by_id.get(contact_uuid)
        linkedin_url = (contact.linkedin_url or "").strip() if contact else ""
        invitation = lead["invitation"].strip()
        # HeyReach exige une URL LinkedIn ET une invitation.
        if not contact or not linkedin_url or not invitation:
            skipped += 1
            continue
        company_name = contact.company.name if contact.company else ""
        rows_to_write.append(
            [
                contact.first_name,
                contact.last_name,
                contact.linkedin_url or "",
                company_name,
                lead["brand"],
                lead["invitation"],
                lead["dm_followup"],
                lead["final_relance"],
            ]
        )

    # Les lead_id non resolus en UUID (pas de contact) comptent aussi comme skip.
    skipped += len(leads) - len(uuid_to_lead)

    # Tri stable : brand puis last_name (sortie deterministe).
    rows_to_write.sort(key=lambda r: (r[4], r[1].lower()))

    # 5) Serialiser en CSV. On ne logge JAMAIS le contenu ni la PII (DC6) — compteurs seuls.
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEYREACH_CSV_HEADER)
    writer.writerows(rows_to_write)
    csv_text = buffer.getvalue()

    logger.info(
        "[DraftsReview] Export HeyReach brand=%s rows=%d skipped=%d",
        brand or "all",
        len(rows_to_write),
        skipped,
    )

    filename = f"heyreach_{brand or 'all'}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Skipped-Count": str(skipped),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Skipped-Count",
        },
    )


@router.get("/{draft_id}", response_model=DraftReview)
async def get_draft(
    draft_id: str,
    user: User = Depends(get_current_user),
    compass: CompassClient = Depends(get_compass_client),
) -> DraftReview:
    """Recupere un draft (proxy vers compass GET /v1/drafts/{id}). 404 si absent."""
    try:
        row = await compass.get_draft(draft_id)
    except (
        CompassNotConfiguredError,
        CompassNotFoundError,
        CompassServiceError,
    ) as exc:
        _raise_for_compass_error(exc)

    return DraftReview.model_validate(row)


@router.patch("/{draft_id}/status", response_model=DraftReview)
async def update_draft_status(
    draft_id: str,
    payload: DraftStatusUpdateIn,
    user: User = Depends(get_current_user),
    compass: CompassClient = Depends(get_compass_client),
) -> DraftReview:
    """Met a jour le statut d'un draft (proxy vers compass PATCH /v1/drafts/{id}/status).

    Le `reviewer` est impose server-side a `current_user.email` (DC18) : on ne
    fait JAMAIS confiance a un reviewer fourni par le client. 404 si absent.
    """
    try:
        row = await compass.update_draft_status(
            draft_id=draft_id,
            status=payload.status,
            reviewer=user.email,
        )
    except (
        CompassNotConfiguredError,
        CompassNotFoundError,
        CompassServiceError,
    ) as exc:
        _raise_for_compass_error(exc)

    return DraftReview.model_validate(row)
