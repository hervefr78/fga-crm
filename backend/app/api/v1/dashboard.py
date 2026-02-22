# =============================================================================
# FGA CRM - Dashboard API (stats agregees)
# =============================================================================

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.task import Task
from app.models.user import User
from app.schemas.dashboard import ActivityByType, DashboardStats, DealsByStage

router = APIRouter()

# Stages consideres comme "pipeline ouvert" (ni gagne ni perdu)
PIPELINE_STAGES = {"new", "contacted", "meeting", "proposal", "negotiation"}


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
    )
