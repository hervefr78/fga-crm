# =============================================================================
# FGA CRM - Companies Routes
# =============================================================================

import contextlib
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import (
    apply_ownership_filter,
    apply_tenant_filter,
    check_entity_access,
    check_tenant_access,
)
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.user import User
from app.schemas.company import (
    SIZE_RANGES,
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
)
from app.schemas.import_export import (
    CompanyImportRequest,
    CompanyImportRow,
    ImportResult,
    ImportRowError,
)

router = APIRouter()


async def _fetch_audit_flags(
    db: AsyncSession,
    company_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, dict], dict[uuid.UUID, int]]:
    """Retourner (audit_map, score_map) pour une liste de company_ids."""
    audit_map: dict[uuid.UUID, dict] = {}
    score_map: dict[uuid.UUID, int] = {}
    if not company_ids:
        return audit_map, score_map

    audit_query = (
        select(
            Activity.company_id,
            Activity.metadata_["audit_type"].as_string().label("audit_type"),
            Activity.metadata_["total_score"].as_string().label("total_score"),
            Activity.metadata_["messaging_score"].as_string().label("messaging_score"),
        )
        .where(
            Activity.company_id.in_(company_ids),
            Activity.type == "audit",
            Activity.metadata_["audit_type"] != None,  # noqa: E711
        )
    )
    audit_rows = (await db.execute(audit_query)).all()

    for row in audit_rows:
        cid = row.company_id
        atype = row.audit_type
        if cid not in audit_map:
            audit_map[cid] = {"has_messaging": False, "has_detailed": False, "has_geo": False}
        if atype == "messaging":
            audit_map[cid]["has_messaging"] = True
            if row.messaging_score and cid not in score_map:
                with contextlib.suppress(ValueError, TypeError):
                    score_map[cid] = int(float(row.messaging_score))
        elif atype == "detailed":
            audit_map[cid]["has_detailed"] = True
            if row.total_score:
                with contextlib.suppress(ValueError, TypeError):
                    score_val = int(float(row.total_score))
                    if cid not in score_map or score_val > score_map[cid]:
                        score_map[cid] = score_val
        elif atype == "geo":
            audit_map[cid]["has_geo"] = True

    return audit_map, score_map


def _company_to_response(
    c: Company,
    owner_name: str | None = None,
    updated_by_name: str | None = None,
    has_audit_messaging: bool = False,
    has_audit_detailed: bool = False,
    has_audit_geo: bool = False,
    audit_score: int | None = None,
) -> CompanyResponse:
    """Convertir un modele Company en schema de reponse (DC8 — centralise)."""
    return CompanyResponse(
        id=str(c.id),
        name=c.name,
        domain=c.domain,
        website=c.website,
        industry=c.industry,
        description=c.description,
        size_range=c.size_range,
        linkedin_url=c.linkedin_url,
        phone=c.phone,
        address_line=c.address_line,
        postal_code=c.postal_code,
        city=c.city,
        country=c.country,
        startup_radar_id=c.startup_radar_id,
        lead_source=c.lead_source,
        vat_number=c.vat_number,
        owner_id=str(c.owner_id) if c.owner_id else None,
        owner_name=owner_name,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
        updated_by_name=updated_by_name,
        has_audit_messaging=has_audit_messaging,
        has_audit_detailed=has_audit_detailed,
        has_audit_geo=has_audit_geo,
        audit_score=audit_score,
        siren=c.siren,
        funding_date=c.funding_date.isoformat() if c.funding_date else None,
        funding_amount=c.funding_amount,
        funding_series=c.funding_series,
        funding_sources=c.funding_sources,
    )


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=5000),
    search: str | None = Query(None, max_length=255),
    industry: str | None = None,
    size_range: str | None = None,
    country: str | None = None,
    lead_source: str | None = Query(None, max_length=100),
    sort_by: str | None = Query(None, max_length=20),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    # Funding multi-source filters (Phase B 2026-05)
    funding_series: str | None = Query(None, max_length=50),
    funding_amount_min: int | None = Query(None, ge=0),  # euros
    funding_date_after: str | None = Query(None, max_length=10),  # ISO YYYY-MM-DD
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Company)
    query = apply_tenant_filter(query, Company, user)
    query = apply_ownership_filter(query, Company, user)

    if search:
        query = query.where(Company.name.ilike(f"%{search}%"))
    if industry:
        query = query.where(Company.industry.ilike(f"%{industry}%"))
    if size_range:
        if size_range not in SIZE_RANGES:
            raise HTTPException(status_code=422, detail=f"size_range invalide. Valeurs : {', '.join(sorted(SIZE_RANGES))}")
        query = query.where(Company.size_range == size_range)
    if country:
        query = query.where(Company.country.ilike(f"%{country}%"))
    if lead_source:
        # Startup Radar : les entreprises existantes n'ont pas lead_source mais ont startup_radar_id
        if lead_source == "startup_radar":
            query = query.where(Company.startup_radar_id.is_not(None))
        else:
            query = query.where(Company.lead_source == lead_source)
    # --- Funding filters ---
    if funding_series:
        query = query.where(Company.funding_series == funding_series)
    if funding_amount_min:
        query = query.where(Company.funding_amount >= funding_amount_min)
    if funding_date_after:
        try:
            after_date = date.fromisoformat(funding_date_after)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=422,
                detail=f"funding_date_after invalide (ISO YYYY-MM-DD attendu) : {e}",
            ) from e
        query = query.where(Company.funding_date >= after_date)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Tri dynamique
    _SORTABLE = {"name", "industry", "size_range", "created_at"}
    if sort_by in _SORTABLE:
        if sort_by == "size_range":
            sort_col = case(
                {"1-10": 1, "11-50": 2, "51-200": 3, "201-500": 4, "500+": 5},
                value=Company.size_range,
                else_=6,
            )
        else:
            sort_col = getattr(Company, sort_by)
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    else:
        query = query.order_by(Company.created_at.desc())

    # Paginate
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    companies = result.scalars().all()

    # Charger les flags d'audit SR et score pour les companies de cette page
    company_ids = [c.id for c in companies]
    audit_map, score_map = await _fetch_audit_flags(db, company_ids)

    return CompanyListResponse(
        items=[
            _company_to_response(
                c,
                has_audit_messaging=audit_map.get(c.id, {}).get("has_messaging", False),
                has_audit_detailed=audit_map.get(c.id, {}).get("has_detailed", False),
                has_audit_geo=audit_map.get(c.id, {}).get("has_geo", False),
                audit_score=score_map.get(c.id),
            )
            for c in companies
        ],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


def _parse_funding_date(payload: dict) -> None:
    """Convertir funding_date str → date.fromisoformat dans le payload.

    Mute le dict en place. Si la conversion echoue, leve HTTPException 422
    (cf. ADR-001 : Pydantic stocke en str, SQLAlchemy attend un objet date natif).
    """
    if "funding_date" in payload and payload["funding_date"]:
        try:
            payload["funding_date"] = date.fromisoformat(payload["funding_date"])
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=422,
                detail=f"funding_date invalide (ISO YYYY-MM-DD attendu) : {e}",
            ) from e


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = data.model_dump()
    _parse_funding_date(payload)
    company = Company(**payload, owner_id=user.id, organization_id=user.organization_id)
    db.add(company)
    await db.flush()
    await db.refresh(company)

    return _company_to_response(company, owner_name=user.full_name)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise non trouvee")
    check_tenant_access(company, user)
    check_entity_access(company, user)

    # Charger le nom du owner et du dernier modificateur
    owner_name = None
    if company.owner_id:
        owner_result = await db.execute(select(User.full_name).where(User.id == company.owner_id))
        owner_name = owner_result.scalar_one_or_none()

    updated_by_name = None
    if company.updated_by:
        ub_result = await db.execute(select(User.full_name).where(User.id == company.updated_by))
        updated_by_name = ub_result.scalar_one_or_none()

    audit_map, score_map = await _fetch_audit_flags(db, [company.id])
    return _company_to_response(
        company,
        owner_name=owner_name,
        updated_by_name=updated_by_name,
        has_audit_messaging=audit_map.get(company.id, {}).get("has_messaging", False),
        has_audit_detailed=audit_map.get(company.id, {}).get("has_detailed", False),
        has_audit_geo=audit_map.get(company.id, {}).get("has_geo", False),
        audit_score=score_map.get(company.id),
    )


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise non trouvee")
    check_tenant_access(company, user)
    check_entity_access(company, user)

    update_data = data.model_dump(exclude_unset=True)
    _parse_funding_date(update_data)
    for field, value in update_data.items():
        setattr(company, field, value)

    # Tracer qui a modifie
    company.updated_by = user.id

    await db.flush()
    await db.refresh(company)

    # Charger owner_name (peut etre different de l'utilisateur courant)
    owner_name = None
    if company.owner_id:
        owner_result = await db.execute(select(User.full_name).where(User.id == company.owner_id))
        owner_name = owner_result.scalar_one_or_none()

    return _company_to_response(company, owner_name=owner_name, updated_by_name=user.full_name)


@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise non trouvee")
    check_tenant_access(company, user)
    check_entity_access(company, user)

    await db.delete(company)


@router.post("/import", response_model=ImportResult)
async def import_companies(
    data: CompanyImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import batch d'entreprises depuis un CSV parse cote client."""
    imported = 0
    errors: list[ImportRowError] = []

    for idx, row_data in enumerate(data.rows, start=1):
        try:
            validated = CompanyImportRow(**row_data)
            company = Company(
                **validated.model_dump(), owner_id=user.id,
                organization_id=user.organization_id,
            )
            db.add(company)
            imported += 1
        except ValidationError as e:
            for err in e.errors():
                errors.append(ImportRowError(
                    row=idx,
                    field=str(err["loc"][-1]) if err["loc"] else "unknown",
                    message=err["msg"],
                ))
        except Exception as e:
            errors.append(ImportRowError(row=idx, field="unknown", message=str(e)))

    if imported > 0:
        await db.flush()

    return ImportResult(imported=imported, errors=errors)
