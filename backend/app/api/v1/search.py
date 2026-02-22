# =============================================================================
# FGA CRM - Recherche Globale
# =============================================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter
from app.db.session import get_db
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User
from app.schemas.search import GlobalSearchResponse, SearchResultItem

router = APIRouter()

MAX_PER_ENTITY = 5


@router.get("", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recherche globale multi-entites (contacts, companies, deals)."""
    search_filter = f"%{q}%"

    # Contacts — select minimal (DC6) + filtre ownership
    contacts_q = select(Contact.id, Contact.first_name, Contact.last_name, Contact.email).where(
        (Contact.first_name.ilike(search_filter))
        | (Contact.last_name.ilike(search_filter))
        | (Contact.email.ilike(search_filter))
    )
    contacts_q = apply_ownership_filter(contacts_q, Contact, user)
    contacts_q = contacts_q.limit(MAX_PER_ENTITY)
    contacts_result = await db.execute(contacts_q)
    contacts = [
        SearchResultItem(
            id=str(r.id),
            label=f"{r.first_name} {r.last_name}".strip(),
            sub=r.email,
        )
        for r in contacts_result
    ]

    # Companies — select minimal (DC6) + filtre ownership
    companies_q = select(Company.id, Company.name, Company.domain).where(
        (Company.name.ilike(search_filter))
        | (Company.domain.ilike(search_filter))
    )
    companies_q = apply_ownership_filter(companies_q, Company, user)
    companies_q = companies_q.limit(MAX_PER_ENTITY)
    companies_result = await db.execute(companies_q)
    companies = [
        SearchResultItem(id=str(r.id), label=r.name, sub=r.domain)
        for r in companies_result
    ]

    # Deals — select minimal (DC6) + filtre ownership
    deals_q = select(Deal.id, Deal.title, Deal.stage).where(Deal.title.ilike(search_filter))
    deals_q = apply_ownership_filter(deals_q, Deal, user)
    deals_q = deals_q.limit(MAX_PER_ENTITY)
    deals_result = await db.execute(deals_q)
    deals = [
        SearchResultItem(id=str(r.id), label=r.title, sub=r.stage)
        for r in deals_result
    ]

    return GlobalSearchResponse(
        contacts=contacts,
        companies=companies,
        deals=deals,
    )
