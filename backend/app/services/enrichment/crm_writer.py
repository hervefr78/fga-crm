# =============================================================================
# FGA CRM - Enrichissement : promotion en contact CRM (ecriture interne)
# =============================================================================
"""Upsert societe + contact dans les tables CRM (source de verite). La sortie du
pipeline EST un contact CRM natif (spec §6). Ecriture interne (plus un appel MCP)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company as CrmCompany
from app.models.contact import Contact
from app.services.enrichment.ports import Company, PersonCandidate

_DECISION_ROLES = frozenset({"CTO", "CPO", "CMO", "FOUNDER"})


async def _find_or_create_company(db: AsyncSession, company: Company) -> CrmCompany:
    """Retrouve la societe par siren puis domaine, sinon la cree."""
    found: CrmCompany | None = None
    if company.siren:
        found = (
            await db.execute(select(CrmCompany).where(CrmCompany.siren == company.siren))
        ).scalars().first()
    if found is None and company.domain:
        found = (
            await db.execute(select(CrmCompany).where(CrmCompany.domain == company.domain))
        ).scalars().first()
    if found is None:
        found = CrmCompany(name=company.name, siren=company.siren, domain=company.domain)
        db.add(found)
        await db.flush()
    return found


async def upsert_contact(
    db: AsyncSession,
    *,
    company: Company,
    person: PersonCandidate,
    email: str,
    email_status: str,
) -> uuid.UUID:
    """Cree/maj la societe + le contact (dedup par email). Retourne contact_id."""
    crm_company = await _find_or_create_company(db, company)

    contact: Contact | None = None
    if email:
        contact = (
            await db.execute(select(Contact).where(Contact.email == email))
        ).scalars().first()
    if contact is None:
        contact = Contact(first_name=person.first_name, last_name=person.last_name)
        db.add(contact)

    contact.first_name = person.first_name
    contact.last_name = person.last_name
    contact.email = email
    contact.email_status = email_status
    contact.title = person.title_raw
    contact.is_decision_maker = person.role in _DECISION_ROLES
    contact.linkedin_url = person.linkedin_url
    contact.source = "enrichment"
    contact.enrichment_source = person.source
    contact.company_id = crm_company.id
    await db.flush()
    return contact.id
