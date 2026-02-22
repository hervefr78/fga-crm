# =============================================================================
# FGA CRM - Companies Routes
# =============================================================================

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.company import Company
from app.models.user import User

router = APIRouter()


class CompanyCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    size_range: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    domain: Optional[str]
    website: Optional[str]
    industry: Optional[str]
    description: Optional[str]
    size_range: Optional[str]
    linkedin_url: Optional[str]
    phone: Optional[str]
    owner_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    items: list[CompanyResponse]
    total: int
    page: int
    size: int
    pages: int


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    industry: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Company)

    if search:
        query = query.where(Company.name.ilike(f"%{search}%"))
    if industry:
        query = query.where(Company.industry == industry)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Company.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    companies = result.scalars().all()

    return CompanyListResponse(
        items=[
            CompanyResponse(
                id=str(c.id), name=c.name, domain=c.domain, website=c.website,
                industry=c.industry, description=c.description, size_range=c.size_range,
                linkedin_url=c.linkedin_url, phone=c.phone,
                owner_id=str(c.owner_id) if c.owner_id else None,
                created_at=c.created_at.isoformat(),
            )
            for c in companies
        ],
        total=total, page=page, size=size, pages=(total + size - 1) // size,
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

    return CompanyResponse(
        id=str(company.id), name=company.name, domain=company.domain,
        website=company.website, industry=company.industry,
        description=company.description, size_range=company.size_range,
        linkedin_url=company.linkedin_url, phone=company.phone,
        owner_id=str(company.owner_id) if company.owner_id else None,
        created_at=company.created_at.isoformat(),
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return CompanyResponse(
        id=str(company.id), name=company.name, domain=company.domain,
        website=company.website, industry=company.industry,
        description=company.description, size_range=company.size_range,
        linkedin_url=company.linkedin_url, phone=company.phone,
        owner_id=str(company.owner_id) if company.owner_id else None,
        created_at=company.created_at.isoformat(),
    )


@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    await db.delete(company)
