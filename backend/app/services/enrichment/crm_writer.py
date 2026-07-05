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


async def _find_or_create_company(
    db: AsyncSession, company: Company, organization_id: uuid.UUID
) -> CrmCompany:
    """Retrouve la societe par siren puis domaine (DANS l'org), sinon la cree."""
    found: CrmCompany | None = None
    if company.siren:
        found = (
            await db.execute(select(CrmCompany).where(
                CrmCompany.siren == company.siren,
                CrmCompany.organization_id == organization_id,
            ))
        ).scalars().first()
    if found is None and company.domain:
        found = (
            await db.execute(select(CrmCompany).where(
                CrmCompany.domain == company.domain,
                CrmCompany.organization_id == organization_id,
            ))
        ).scalars().first()
    if found is None:
        found = CrmCompany(
            name=company.name, siren=company.siren, domain=company.domain,
            organization_id=organization_id,
        )
        db.add(found)
        await db.flush()
    return found


async def upsert_contact(
    db: AsyncSession,
    *,
    company: Company,
    person: PersonCandidate,
    email: str | None,
    email_status: str,
    organization_id: uuid.UUID,
) -> uuid.UUID:
    """Cree/maj la societe + le contact. Retourne contact_id.

    email peut etre None : on enregistre alors un decideur SANS email (nom + role
    + LinkedIn), a completer plus tard. Le dedup par email n'a lieu que si un email
    est fourni ; sinon on cree un nouveau contact (email nullable, non-unique)."""
    crm_company = await _find_or_create_company(db, company, organization_id)

    contact: Contact | None = None
    if email:
        contact = (
            await db.execute(select(Contact).where(
                Contact.email == email,
                Contact.organization_id == organization_id,
            ))
        ).scalars().first()
    # Dedup par LinkedIn : meme personne deja enregistree (typiquement un decideur
    # ecrit SANS email lors d'un enrichissement precedent) -> on la MET A JOUR au
    # lieu de creer un doublon (idempotence de la re-enrichissement).
    if contact is None and person.linkedin_url:
        contact = (
            await db.execute(select(Contact).where(
                Contact.linkedin_url == person.linkedin_url,
                Contact.organization_id == organization_id,
            ))
        ).scalars().first()
    if contact is None:
        contact = Contact(
            first_name=person.first_name, last_name=person.last_name,
            organization_id=organization_id,
        )
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


def _domain_from_email(email: str) -> str | None:
    if not email or email.count("@") != 1:
        return None
    return (email.split("@", 1)[1].strip().lower()) or None


async def update_contact_email(
    db: AsyncSession,
    *,
    contact_id: uuid.UUID,
    email: str,
    email_status: str,
    organization_id: uuid.UUID,
    verified_by_icypeas: bool = True,
    source: str = "icypeas",
    backfill_domain: bool = True,
) -> uuid.UUID | None:
    """Feature B : met a jour un contact EXISTANT (email + statut + flag Icypeas).

    Backfille le domaine de la societe liee si Icypeas a resolu un domaine inedit
    (email pro valide). Retourne contact_id, ou None si contact absent / hors org."""
    contact = (
        await db.execute(select(Contact).where(
            Contact.id == contact_id,
            Contact.organization_id == organization_id,
        ))
    ).scalars().first()
    if contact is None:
        return None  # inexistant ou cross-org -> no-op (isolation)

    contact.email = email
    contact.email_status = email_status
    contact.email_verified_by_icypeas = verified_by_icypeas
    contact.enrichment_source = source

    # Backfill domaine societe depuis l'email valide par Icypeas (si absent),
    # en evitant la collision (organization_id, domain).
    dom = _domain_from_email(email)
    if backfill_domain and dom and verified_by_icypeas and contact.company_id:
        company = await db.get(CrmCompany, contact.company_id)
        if company is not None and company.organization_id == organization_id and not company.domain:
            clash = (
                await db.execute(select(CrmCompany.id).where(
                    CrmCompany.domain == dom,
                    CrmCompany.organization_id == organization_id,
                ))
            ).first()
            if clash is None:
                company.domain = dom
                company.domain_verified_by_icypeas = True

    await db.flush()
    return contact.id
