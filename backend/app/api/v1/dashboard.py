# =============================================================================
# FGA CRM - Dashboard API (stats agregees)
# =============================================================================

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import PERIOD_TO_MONTHS, PIPELINE_STAGES, Deal
from app.models.task import Task
from app.models.user import User
from app.schemas.ai import NextActionAction, NextActionResponse
from app.schemas.dashboard import ActivityByType, DashboardStats, DealsByStage

router = APIRouter()

# Limite globale des suggestions retournees (DC1 — borne en sortie)
MAX_NEXT_ACTIONS = 3


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourner les statistiques agregees pour le dashboard."""
    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # --- Contacts ---
    contacts_q = apply_ownership_filter(
        select(func.count(Contact.id)), Contact, current_user
    )
    contacts_total = (await db.execute(contacts_q)).scalar() or 0

    contacts_month_q = apply_ownership_filter(
        select(func.count(Contact.id)).where(Contact.created_at >= month_start),
        Contact, current_user,
    )
    contacts_this_month = (await db.execute(contacts_month_q)).scalar() or 0

    # --- Companies ---
    companies_q = apply_ownership_filter(
        select(func.count(Company.id)), Company, current_user
    )
    companies_total = (await db.execute(companies_q)).scalar() or 0

    # --- Deals : total ---
    deals_q = apply_ownership_filter(
        select(func.count(Deal.id)), Deal, current_user
    )
    deals_total = (await db.execute(deals_q)).scalar() or 0

    # --- Deals : pipeline amount (hors won/lost) ---
    pipeline_q = apply_ownership_filter(
        select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
            Deal.stage.in_(PIPELINE_STAGES)
        ),
        Deal, current_user,
    )
    deals_pipeline_amount = float((await db.execute(pipeline_q)).scalar() or 0)

    # --- Deals : won ---
    won_q = apply_ownership_filter(
        select(
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.amount), 0.0),
        ).where(Deal.stage == "won"),
        Deal, current_user,
    )
    won_row = (await db.execute(won_q)).one()
    deals_won_count = won_row[0] or 0
    deals_won_amount = float(won_row[1] or 0)

    # --- Deals : lost ---
    lost_q = apply_ownership_filter(
        select(func.count(Deal.id)).where(Deal.stage == "lost"),
        Deal, current_user,
    )
    deals_lost_count = (await db.execute(lost_q)).scalar() or 0

    # --- Deals par stage (bar chart) ---
    stage_q = apply_ownership_filter(
        select(
            Deal.stage,
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.amount), 0.0),
        ).group_by(Deal.stage),
        Deal, current_user,
    )
    stage_rows = (await db.execute(stage_q)).all()
    deals_by_stage = [
        DealsByStage(stage=row[0], count=row[1], total_amount=float(row[2]))
        for row in stage_rows
    ]

    # --- Activites par type (30 derniers jours) ---
    act_q = apply_ownership_filter(
        select(Activity.type, func.count(Activity.id))
        .where(Activity.created_at >= thirty_days_ago)
        .group_by(Activity.type),
        Activity, current_user, owner_field="user_id",
    )
    act_rows = (await db.execute(act_q)).all()
    activities_by_type = [
        ActivityByType(type=row[0], count=row[1]) for row in act_rows
    ]
    activities_total_30d = sum(a.count for a in activities_by_type)

    # --- Taches ---
    tasks_total_q = apply_ownership_filter(
        select(func.count(Task.id)), Task, current_user, owner_field="assigned_to",
    )
    tasks_total = (await db.execute(tasks_total_q)).scalar() or 0

    tasks_completed_q = apply_ownership_filter(
        select(func.count(Task.id)).where(Task.is_completed.is_(True)),
        Task, current_user, owner_field="assigned_to",
    )
    tasks_completed = (await db.execute(tasks_completed_q)).scalar() or 0

    tasks_overdue_q = apply_ownership_filter(
        select(func.count(Task.id)).where(
            Task.is_completed.is_(False),
            Task.due_date < func.now(),
        ),
        Task, current_user, owner_field="assigned_to",
    )
    tasks_overdue = (await db.execute(tasks_overdue_q)).scalar() or 0

    # --- Emails envoyes (30 derniers jours) ---
    emails_q = apply_ownership_filter(
        select(func.count(Activity.id)).where(
            Activity.type == "email",
            Activity.created_at >= thirty_days_ago,
        ),
        Activity, current_user, owner_field="user_id",
    )
    emails_sent_30d = (await db.execute(emails_q)).scalar() or 0

    # --- KPI pricing : MRR / ARR / one-shot (DC6 select minimal, RBAC applique) ---
    # On charge uniquement les 3 colonnes utiles puis on normalise en Python.
    pricing_won_q = apply_ownership_filter(
        select(Deal.pricing_type, Deal.amount, Deal.recurring_amount).where(
            Deal.stage == "won"
        ),
        Deal, current_user,
    )
    # Pipeline : on n'a pas besoin de Deal.amount (one_shot pipeline ne contribue pas au MRR)
    pricing_pipeline_q = apply_ownership_filter(
        select(Deal.pricing_type, Deal.recurring_amount).where(
            Deal.stage.in_(PIPELINE_STAGES)
        ),
        Deal, current_user,
    )
    won_rows = (await db.execute(pricing_won_q)).all()
    pipeline_rows = (await db.execute(pricing_pipeline_q)).all()

    deals_mrr_won = 0.0
    deals_one_shot_won = 0.0
    for ptype, amount, rec_amount in won_rows:
        if ptype == "one_shot":
            deals_one_shot_won += float(amount or 0.0)
            continue
        # Recurrent : ne contribue au MRR que si recurring_amount renseigne
        months = PERIOD_TO_MONTHS.get(ptype)
        if months and rec_amount is not None:
            deals_mrr_won += float(rec_amount) / months

    deals_mrr_pipeline = 0.0
    for ptype, rec_amount in pipeline_rows:
        if ptype == "one_shot":
            continue
        months = PERIOD_TO_MONTHS.get(ptype)
        if months and rec_amount is not None:
            deals_mrr_pipeline += float(rec_amount) / months

    deals_arr_won = deals_mrr_won * 12

    return DashboardStats(
        contacts_total=contacts_total,
        contacts_this_month=contacts_this_month,
        companies_total=companies_total,
        deals_total=deals_total,
        deals_pipeline_amount=deals_pipeline_amount,
        deals_won_amount=deals_won_amount,
        deals_won_count=deals_won_count,
        deals_lost_count=deals_lost_count,
        deals_by_stage=deals_by_stage,
        activities_by_type=activities_by_type,
        activities_total_30d=activities_total_30d,
        tasks_total=tasks_total,
        tasks_completed=tasks_completed,
        tasks_overdue=tasks_overdue,
        emails_sent_30d=emails_sent_30d,
        deals_mrr_won=deals_mrr_won,
        deals_arr_won=deals_arr_won,
        deals_mrr_pipeline=deals_mrr_pipeline,
        deals_one_shot_won=deals_one_shot_won,
    )


# ---------------------------------------------------------------------------
# Next-actions agregees (mock rule-based, pas de LLM)
# ---------------------------------------------------------------------------

@router.get("/next-actions", response_model=list[NextActionResponse])
async def get_dashboard_next_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NextActionResponse]:
    """Suggestions hebdomadaires agregees pour le dashboard.

    Logique entierement rule-based (pas d'appel LLM). Calcul de signaux sur
    les entites visibles par l'utilisateur (RBAC via apply_ownership_filter).

    Renvoie au plus 3 suggestions, dans l'ordre de priorite suivant :
        1. Taches en retard
        2. Deals chauds bloques (proposal/negotiation sans activity 7j)
        3. Contacts qualifies stale (sans activity 14j)
        4. Pipeline a closer dans les 7 prochains jours

    Liste vide => le frontend masque l'AI card.
    """
    suggestions: list[NextActionResponse] = []
    today = date.today()
    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)
    in_seven_days = today + timedelta(days=7)

    # 1. Taches en retard (assignees a l'utilisateur, ou toutes pour manager/admin)
    overdue_q = apply_ownership_filter(
        select(func.count(Task.id)).where(
            Task.is_completed.is_(False),
            Task.due_date < func.now(),
        ),
        Task, current_user, owner_field="assigned_to",
    )
    overdue = (await db.execute(overdue_q)).scalar() or 0
    if overdue > 0:
        suggestions.append(NextActionResponse(
            title="Reprendre le controle des taches en retard",
            body=f"{overdue} tache(s) en retard. Prioriser celles liees aux deals chauds.",
            primary_action=NextActionAction(label="Voir les taches", type="view"),
        ))

    # 2. Deals chauds bloques : stage proposal/negotiation sans activity dans les 7j
    recent_act_deal_subq = (
        select(Activity.deal_id)
        .where(
            Activity.created_at >= seven_days_ago,
            Activity.deal_id.is_not(None),
        )
        .distinct()
    )
    hot_blocked_q = apply_ownership_filter(
        select(func.count(Deal.id)).where(
            Deal.stage.in_(["proposal", "negotiation"]),
            Deal.id.not_in(recent_act_deal_subq),
        ),
        Deal, current_user,
    )
    hot_blocked = (await db.execute(hot_blocked_q)).scalar() or 0
    if hot_blocked > 0:
        suggestions.append(NextActionResponse(
            title=f"Reactiver {hot_blocked} deal(s) chaud(s)",
            body=(
                f"Aucune activite depuis 7 jours sur {hot_blocked} deal(s) "
                "en proposition/negociation."
            ),
            primary_action=NextActionAction(label="Voir le pipeline", type="view"),
        ))

    # 3. Contacts qualifies stale : status=qualified sans activity dans les 14j
    recent_act_contact_subq = (
        select(Activity.contact_id)
        .where(
            Activity.created_at >= fourteen_days_ago,
            Activity.contact_id.is_not(None),
        )
        .distinct()
    )
    stale_contacts_q = apply_ownership_filter(
        select(func.count(Contact.id)).where(
            Contact.status == "qualified",
            Contact.id.not_in(recent_act_contact_subq),
        ),
        Contact, current_user,
    )
    stale_contacts = (await db.execute(stale_contacts_q)).scalar() or 0
    if stale_contacts > 0:
        suggestions.append(NextActionResponse(
            title=f"Relancer {stale_contacts} contact(s) qualifie(s) sans suivi",
            body="Risque de refroidissement : aucun contact depuis 14 jours.",
            primary_action=NextActionAction(label="Voir les contacts", type="view"),
        ))

    # 4. Pipeline a closer cette semaine (calcule seulement si on a < MAX suggestions)
    if len(suggestions) < MAX_NEXT_ACTIONS:
        close_q = apply_ownership_filter(
            select(func.count(Deal.id)).where(
                Deal.stage.in_(PIPELINE_STAGES),
                Deal.expected_close_date.is_not(None),
                Deal.expected_close_date >= today,
                Deal.expected_close_date <= in_seven_days,
            ),
            Deal, current_user,
        )
        close_imminent = (await db.execute(close_q)).scalar() or 0
        if close_imminent > 0:
            suggestions.append(NextActionResponse(
                title="Closer cette semaine",
                body=(
                    f"{close_imminent} deal(s) avec date de cloture prevue "
                    "dans les 7 prochains jours."
                ),
                primary_action=NextActionAction(label="Voir le pipeline", type="view"),
            ))

    return suggestions[:MAX_NEXT_ACTIONS]
