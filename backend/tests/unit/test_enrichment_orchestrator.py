"""Test E2E de l'orchestrateur d'enrichissement (providers mock, sans reseau)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.enrichment import (
    EnrichmentEmailVerification,
    EnrichmentJob,
    EnrichmentProvenance,
)
from app.services.enrichment import freshness, orchestrator
from app.services.enrichment.orchestrator import run_enrichment_job


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch: pytest.MonkeyPatch):
    async def _noop(*a, **k):
        return None

    async def _never_fresh(*a, **k):
        return False

    monkeypatch.setattr(freshness, "touch", _noop)
    monkeypatch.setattr(freshness, "is_fresh", _never_fresh)


async def test_run_enrichment_job_company_mode(db_session: AsyncSession, test_org):
    job = EnrichmentJob(
        mode="company", status="queued",
        target_json={"kind": "company", "siren": "123456789"},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()

    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    stats = refreshed.stats_json
    assert stats["companies"] == 1
    assert stats["people_found"] == 3          # CTO/CPO/CMO (mock, 1 par role)
    assert stats["emails_found"] >= 1
    assert stats["valid"] >= 1

    # Contacts CRM crees (source enrichment)
    contacts = (
        await db_session.execute(select(Contact).where(Contact.source == "enrichment"))
    ).scalars().all()
    assert len(contacts) >= 1
    assert all(c.is_decision_maker for c in contacts)  # CTO/CPO/CMO
    assert all(c.title for c in contacts)

    # Verifications + provenance tracees
    n_verif = (
        await db_session.execute(select(func.count()).select_from(EnrichmentEmailVerification))
    ).scalar()
    n_prov = (
        await db_session.execute(select(func.count()).select_from(EnrichmentProvenance))
    ).scalar()
    assert n_verif >= 1
    assert n_prov >= 2   # name + email par contact


async def test_company_saves_decision_makers_without_email(
    db_session: AsyncSession, test_org, monkeypatch
):
    """Decideurs trouves mais SANS email (domaine manquant) : on les enregistre
    quand meme (nom + role + LinkedIn), avec email=None / status not_found."""
    from app.services.enrichment import factory

    class _NoEmailFinder:
        name = "noemail"
        cost_per_hit = 1

        async def find(self, person, domain_or_company):
            return None  # aucun email trouve (ex: pas de domaine)

    monkeypatch.setattr(factory, "get_email_finders", lambda: [_NoEmailFinder()])
    monkeypatch.setattr(orchestrator, "get_email_finders", lambda: [_NoEmailFinder()])

    job = EnrichmentJob(
        mode="company", status="queued",
        target_json={"kind": "company", "siren": "123456789"},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()

    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    stats = refreshed.stats_json
    assert stats["people_found"] == 3          # CTO/CPO/CMO (mock)
    assert stats["emails_found"] == 0          # aucun email
    assert stats["contacts_no_email"] == 3     # les 3 decideurs ecrits sans email
    assert stats["valid"] == 0

    contacts = (
        await db_session.execute(select(Contact).where(Contact.source == "enrichment"))
    ).scalars().all()
    assert len(contacts) == 3
    assert all(c.is_decision_maker for c in contacts)
    assert all(c.email is None for c in contacts)
    assert all(c.email_status == "not_found" for c in contacts)


async def test_no_email_decision_makers_stay_retryable(
    db_session: AsyncSession, test_org, monkeypatch
):
    """Regression : un decideur ecrit SANS email ne doit PAS etre marque 'frais'.
    Sinon il serait gele enrichment_refresh_days (60j) et son email ne pourrait
    jamais etre complete par un run ulterieur (ex: via le domaine du lead, #31).
    -> freshness.touch ne doit PAS etre appele quand aucun email n'est trouve."""
    from app.services.enrichment import factory

    class _NoEmailFinder:
        name = "noemail"
        cost_per_hit = 1

        async def find(self, person, domain_or_company):
            return None  # aucun email (ex: domaine manquant)

    monkeypatch.setattr(factory, "get_email_finders", lambda: [_NoEmailFinder()])
    monkeypatch.setattr(orchestrator, "get_email_finders", lambda: [_NoEmailFinder()])

    touch_calls = {"n": 0}

    async def _spy_touch(*a, **k):
        touch_calls["n"] += 1

    # Remplace le noop du fixture _no_redis par un spy (applique apres le fixture).
    monkeypatch.setattr(freshness, "touch", _spy_touch)

    job = EnrichmentJob(
        mode="company", status="queued",
        target_json={"kind": "company", "siren": "123456789"},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    assert refreshed.stats_json["contacts_no_email"] == 3
    assert refreshed.stats_json["emails_found"] == 0
    # Aucun touch : les 3 decideurs sans email restent retentables (pas geles).
    assert touch_calls["n"] == 0


async def test_upsert_contact_dedup_by_linkedin(db_session: AsyncSession, test_org):
    """Re-enrichissement idempotent : un contact sans email (matche par LinkedIn)
    est MIS A JOUR avec l'email trouve, pas duplique."""
    from app.services.enrichment.crm_writer import upsert_contact
    from app.services.enrichment.ports import Company as PortCompany
    from app.services.enrichment.ports import PersonCandidate

    company = PortCompany(siren="123456789", name="Acme")
    person = PersonCandidate(
        first_name="Jean", last_name="Dupont", title_raw="CTO", source="icypeas",
        linkedin_url="https://linkedin.com/in/jeandupont", role="CTO",
    )
    # 1er passage : sans email (domaine manquant).
    cid1 = await upsert_contact(
        db_session, company=company, person=person, email=None,
        email_status="not_found", organization_id=test_org.id,
    )
    # 2e passage : email trouve, MEME personne (matchee par LinkedIn).
    cid2 = await upsert_contact(
        db_session, company=company, person=person, email="jean@acme.com",
        email_status="valid", organization_id=test_org.id,
    )
    assert cid1 == cid2  # meme contact, pas de doublon
    refreshed = await db_session.get(Contact, cid1)
    assert refreshed.email == "jean@acme.com"
    n = (await db_session.execute(select(func.count()).select_from(Contact))).scalar()
    assert n == 1


async def test_run_enrichment_job_source_mode(db_session: AsyncSession, test_org):
    """Mode source : societes CRM de la provenance, org-scopees, sans-siren comptees."""
    import uuid as _uuid

    from app.models.company import Company as CrmCompany
    from app.models.organization import Organization

    other_org = Organization(id=_uuid.uuid4(), name="Autre", slug=f"o-{_uuid.uuid4().hex[:8]}")
    db_session.add(other_org)
    db_session.add_all([
        # 2 societes de la source ciblee avec siren
        CrmCompany(name="SrcCo1", siren="100000001", lead_source="nomo-ia",
                   organization_id=test_org.id),
        CrmCompany(name="SrcCo2", siren="100000002", lead_source="nomo-ia",
                   website="https://www.acme.fr", organization_id=test_org.id),
        # sans siren : search_by_name (mock ABC) -> None -> skipped_no_siren
        CrmCompany(name="NoSiren", lead_source="nomo-ia", organization_id=test_org.id),
        # bruit : autre provenance + autre org (isolation)
        CrmCompany(name="OtherSrc", siren="100000009", lead_source="plein-phare",
                   organization_id=test_org.id),
        CrmCompany(name="OtherOrg", siren="100000008", lead_source="nomo-ia",
                   organization_id=other_org.id),
    ])
    await db_session.commit()

    job = EnrichmentJob(
        mode="source", status="queued",
        target_json={"kind": "source", "source_filter": {"lead_source": "nomo-ia", "limit": 200}},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    stats = refreshed.stats_json
    assert stats["companies"] == 2            # les 2 avec siren (org + provenance)
    assert stats["skipped_no_siren"] == 1     # NoSiren irresoluble via mock
    assert stats["people_found"] == 6         # 3 decideurs mock par societe


async def test_resolve_source_companies_resolves_missing_siren(
    db_session: AsyncSession, test_org
):
    """Sans siren + search_by_name qui trouve -> resolue ET persistee sur la fiche."""
    from sqlalchemy import select as sa_select

    from app.models.company import Company as CrmCompany
    from app.services.enrichment._pipeline import (
        _parse_target,
        _resolve_source_companies,
    )
    from app.services.enrichment.ports import Company as PortCompany

    class _Src:
        async def search_by_name(self, name: str):
            return PortCompany(siren="999888777", name=name, domain="found.fr")

    db_session.add(CrmCompany(name="NoSirenCo", lead_source="nomo-ia",
                              website="https://www.crm-site.fr/x", organization_id=test_org.id))
    await db_session.commit()

    stats: dict = {}
    target = _parse_target(
        {"kind": "source", "source_filter": {"lead_source": "nomo-ia", "limit": 10}}
    )
    out = await _resolve_source_companies(db_session, test_org.id, target, _Src(), stats)

    assert [c.siren for c in out] == ["999888777"]
    assert out[0].domain == "crm-site.fr"     # domaine CRM normalise prioritaire
    assert stats.get("skipped_no_siren") is None
    row = (
        await db_session.execute(sa_select(CrmCompany).where(CrmCompany.name == "NoSirenCo"))
    ).scalar_one()
    assert row.siren == "999888777"           # persiste (pas de re-resolution future)


async def test_run_enrichment_job_idempotent(db_session: AsyncSession, monkeypatch):
    called = {"n": 0}
    orig = orchestrator._resolve_companies

    async def _spy(*a, **k):
        called["n"] += 1
        return await orig(*a, **k)

    monkeypatch.setattr(orchestrator, "_resolve_companies", _spy)
    job = EnrichmentJob(mode="company", status="done", target_json={"kind": "company", "siren": "1"})
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)  # etat terminal -> no-op
    assert called["n"] == 0


async def test_rgpd_rejects_non_pro_emails(db_session: AsyncSession, monkeypatch, test_org):
    # Force le finder a renvoyer un email perso -> doit etre rejete (aucun contact).
    from app.services.enrichment import factory
    from app.services.enrichment.ports import EmailCandidate

    class _PersoFinder:
        name = "mock"
        cost_per_hit = 1.0

        async def find(self, person, domain):
            return EmailCandidate(email="perso@gmail.com", confidence=0.9, status="valid", source="mock")

    monkeypatch.setattr(factory, "get_email_finders", lambda: [_PersoFinder()])
    # re-importer la ref dans l'orchestrateur (il appelle get_email_finders au runtime)
    monkeypatch.setattr(orchestrator, "get_email_finders", lambda: [_PersoFinder()])

    job = EnrichmentJob(mode="company", status="queued", target_json={"kind": "company", "siren": "999"}, organization_id=test_org.id)
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    # emails trouves mais tous perso -> 0 valid, 0 contact
    assert refreshed.stats_json["valid"] == 0
    contacts = (await db_session.execute(select(func.count()).select_from(Contact))).scalar()
    assert contacts == 0


async def test_freshness_skips_recently_enriched(db_session: AsyncSession, monkeypatch, test_org):
    # is_fresh -> True : la personne a ete enrichie recemment -> skip, aucune depense.
    async def _always_fresh(*a, **k):
        return True

    monkeypatch.setattr(freshness, "is_fresh", _always_fresh)

    job = EnrichmentJob(
        mode="company", status="queued",
        target_json={"kind": "company", "siren": "123456789"},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    stats = refreshed.stats_json
    assert stats["people_found"] > 0
    assert stats["skipped_fresh"] == stats["people_found"]  # tous skippes
    assert stats["emails_found"] == 0                       # aucun email cherche
    assert stats["valid"] == 0
    contacts = (await db_session.execute(select(func.count()).select_from(Contact))).scalar()
    assert contacts == 0


async def test_resolve_companies_dedup_sirens(db_session: AsyncSession):
    # Doublons de sirens (erreur CSV) -> une seule societe par siren (pas de double-paiement).
    from app.services.enrichment.adapters.mock import MockCompanySource
    from app.services.enrichment.ports import TargetSpec

    target = TargetSpec(kind="batch", sirens=["111111111", "111111111", "222222222"])
    companies = await orchestrator._resolve_companies(MockCompanySource(), target)
    assert len(companies) == 2
    assert {c.siren for c in companies} == {"111111111", "222222222"}


async def test_company_failure_is_isolated(db_session: AsyncSession, monkeypatch, test_org):
    # Un provider qui plante sur UNE societe ne fait pas perdre le travail des autres.
    from app.services.enrichment.adapters.mock import MockPeopleSource

    class _FlakyPeople(MockPeopleSource):
        async def find_people(self, company, roles):
            if company.siren == "222222222":
                raise RuntimeError("provider KO")
            return await super().find_people(company, roles)

    monkeypatch.setattr(orchestrator, "get_people_sources", lambda: [_FlakyPeople()])

    job = EnrichmentJob(
        mode="batch", status="queued",
        target_json={"kind": "batch", "sirens": ["111111111", "222222222", "333333333"]},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"          # job global OK malgre l'echec isole
    assert refreshed.stats_json["errors"] == 1  # seule 222222222 a echoue
    # Le travail des societes saines est bien persiste (checkpoint par societe).
    contacts = (await db_session.execute(select(func.count()).select_from(Contact))).scalar()
    assert contacts >= 1
