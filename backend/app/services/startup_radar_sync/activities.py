# =============================================================================
# FGA CRM - Startup Radar Sync : Activities funding + Tasks qualification
# create_funding_activity + create_qualification_task (idempotentes)
# =============================================================================

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.task import Task

from ._common import _format_amount_subject


async def create_funding_activity(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    startup_data: dict,
    organization_id: uuid.UUID,
) -> bool:
    """Cree une Activity 'funding_detected' depuis les donnees SR. Idempotente.

    Idempotence : (company_id, type='funding_detected', subject, organization_id)
    — le subject inclut le montant + la serie donc un nouveau round produit une
    nouvelle activity. Scopee a l'org pour l'isolation multi-tenant.

    Retourne True si activity creee, False si elle existait deja ou si pas de montant.
    """
    amount_eur = startup_data.get("amount", 0)
    if not amount_eur:
        return False

    series = startup_data.get("series") or "Levée"
    sources = startup_data.get("source_names") or ["startup_radar"]
    investors = startup_data.get("investors") or []

    subject = _format_amount_subject(amount_eur, series)

    # Flush pour rendre visible les inserts precedents de la session (l'autoflush
    # peut etre desactivee, ex: session de test). Indispensable pour l'idempotence
    # entre appels successifs au sein de la meme transaction.
    await db.flush()

    # Idempotence : verifier si l'activity existe deja (scopee org)
    stmt = select(Activity).where(
        Activity.company_id == company_id,
        Activity.type == "funding_detected",
        Activity.subject == subject,
        Activity.organization_id == organization_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return False

    amount_m = amount_eur / 1_000_000
    # source_urls : dict source_name -> URL article (utile pour click-through
    # depuis la fiche company vers l'article source ayant detecte la levee).
    # SR retourne ca dans GET /startups/{id} (cf. handoff doc section 1.1).
    source_urls = startup_data.get("source_urls") or {}
    metadata = {
        "amount_eur": amount_eur,
        "series": series,
        "sources": sources,
        "source_urls": source_urls if isinstance(source_urls, dict) else {},
        "investors": investors[:10],  # cap pour eviter blob enorme
        "funding_date": startup_data.get("funding_date"),
        "siren": startup_data.get("siren"),
    }

    content_lines = [
        f"Montant : {amount_m:.1f}M€",
        f"Série : {series}",
        f"Sources détectées : {', '.join(sources)}",
    ]
    if investors:
        content_lines.append(f"Investisseurs : {', '.join(investors[:5])}")

    activity = Activity(
        id=uuid.uuid4(),
        type="funding_detected",
        subject=subject,
        content="\n".join(content_lines),
        metadata_=metadata,
        company_id=company_id,
        user_id=user_id,
        organization_id=organization_id,
    )
    db.add(activity)
    # Flush pour que les appels suivants au sein de la meme transaction voient
    # cette activity et appliquent correctement l'idempotence (autoflush=False
    # sur session de test). En prod autoflush=True donc no-op effectif.
    await db.flush()
    return True


async def create_qualification_task(
    db: AsyncSession,
    company_id: uuid.UUID,
    assigned_to: uuid.UUID,
    startup_data: dict,
    organization_id: uuid.UUID,
) -> bool:
    """Cree une Task 'qualification' pour qualifier la levee. Idempotente.

    Le seuil de filtrage est applique cote SR (pipeline funding_ingest) : si la
    startup arrive ici, c'est qu'elle est qualifying. CRM cree donc la task
    systematiquement quand amount > 0.

    Idempotence : (company_id, type='qualification', is_completed=False,
    organization_id) — une seule task ouverte a la fois. Si l'ancienne est
    completee, une nouvelle peut etre creee (ex: nouveau round 6 mois plus tard).
    Scopee a l'org pour l'isolation multi-tenant.

    Retourne True si task creee, False sinon.
    """
    amount_eur = startup_data.get("amount", 0)
    if not amount_eur:
        return False

    # Flush pour rendre visible les inserts precedents (cf. create_funding_activity).
    await db.flush()

    # Idempotence : verifier qu'aucune task qualification ouverte n'existe deja (scopee org)
    stmt = select(Task).where(
        Task.company_id == company_id,
        Task.type == "qualification",
        Task.is_completed.is_(False),
        Task.organization_id == organization_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return False

    amount_m = amount_eur / 1_000_000
    startup_name = startup_data.get("name", "Startup")
    series = startup_data.get("series") or "Levée"
    title = f"Qualifier la levée : {startup_name} ({amount_m:.1f}M€ — {series})"

    # Echeance 7 jours (timezone-naive — DateTime(timezone=True) accepte naive en PG)
    due_date = datetime.utcnow() + timedelta(days=7)

    task = Task(
        id=uuid.uuid4(),
        title=title[:500],  # DC1 — respecter max_length
        type="qualification",
        priority="medium",
        due_date=due_date,
        company_id=company_id,
        assigned_to=assigned_to,
        is_completed=False,
        organization_id=organization_id,
    )
    db.add(task)
    await db.flush()  # cf. note dans create_funding_activity
    return True
