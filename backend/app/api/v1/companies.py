# =============================================================================
# FGA CRM - Companies Routes
# =============================================================================

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter, check_entity_access
from app.db.session import get_db
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


def _company_to_response(c: Company) -> CompanyResponse:
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
        country=c.country,
        city=c.city,
        startup_radar_id=c.startup_radar_id,
        owner_id=str(c.owner_id) if c.owner_id else None,
        created_at=c.created_at.isoformat(),
    )


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    industry: str | None = None,
    size_range: str | None = None,
    country: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Company)
    query = apply_ownership_filter(query, Company, user)

    if search:
        query = query.where(Company.name.ilike(f"%{search}%"))
    if industry:
        query = query.where(Company.industry == industry)
    if size_range:
        if size_range not in SIZE_RANGES:
            raise HTTPException(status_code=422, detail=f"size_range invalide. Valeurs : {', '.join(sorted(SIZE_RANGES))}")
        query = query.where(Company.size_range == size_range)
    if country:
        query = query.where(Company.country.ilike(f"%{country}%"))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Company.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    companies = result.scalars().all()

    return CompanyListResponse(
        items=[_company_to_response(c) for c in companies],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    company = Company(**data.model_dump(), owner_id=user.id)
    db.add(company)
    await db.flush()
    await db.refresh(company)

    return _company_to_response(company)


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
    check_entity_access(company, user)

    return _company_to_response(company)


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
    check_entity_access(company, user)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    await db.flush()
    await db.refresh(company)
    return _company_to_response(company)


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
            company = Company(**validated.model_dump(), owner_id=user.id)
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
