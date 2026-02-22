# =============================================================================
# FGA CRM - Tasks Routes
# =============================================================================

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter, check_entity_access
from app.db.session import get_db
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskCompletionToggle,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter()


def _task_to_response(t: Task) -> TaskResponse:
    """Convertir un modele Task en schema de reponse (DC8 — centralise)."""
    return TaskResponse(
        id=str(t.id),
        title=t.title,
        description=t.description,
        type=t.type,
        priority=t.priority,
        is_completed=t.is_completed,
        due_date=t.due_date.isoformat() if t.due_date else None,
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
        assigned_to=str(t.assigned_to) if t.assigned_to else None,
        contact_id=str(t.contact_id) if t.contact_id else None,
        deal_id=str(t.deal_id) if t.deal_id else None,
        created_at=t.created_at.isoformat(),
    )


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    """Convertir un string en UUID avec gestion d'erreur propre."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field_name} invalide")


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    type: str | None = None,
    priority: str | None = None,
    is_completed: str | None = None,
    overdue: str | None = None,
    assigned_to: str | None = None,
    contact_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Task)
    query = apply_ownership_filter(query, Task, user, owner_field="assigned_to")

    # Filtres
    if search:
        query = query.where(Task.title.ilike(f"%{search}%"))
    if type:
        query = query.where(Task.type == type)
    if priority:
        query = query.where(Task.priority == priority)
    if is_completed == "true":
        query = query.where(Task.is_completed == True)  # noqa: E712
    elif is_completed == "false":
        query = query.where(Task.is_completed == False)  # noqa: E712
    if overdue == "true":
        query = query.where(Task.is_completed == False, Task.due_date < func.now())  # noqa: E712
    if assigned_to:
        query = query.where(Task.assigned_to == _parse_uuid(assigned_to, "assigned_to"))
    if contact_id:
        query = query.where(Task.contact_id == _parse_uuid(contact_id, "contact_id"))

    # Comptage
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Tri : echeance la plus proche d'abord, puis les plus recentes
    query = query.order_by(
        Task.due_date.asc().nullslast(),
        Task.created_at.desc(),
    ).offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[_task_to_response(t) for t in tasks],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 0,
    )


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task_data = data.model_dump()

    # Convertir les FK string → UUID
    for key in ("assigned_to", "contact_id", "deal_id"):
        if task_data.get(key):
            task_data[key] = _parse_uuid(task_data[key], key)

    # Convertir due_date string → datetime
    if task_data.get("due_date"):
        try:
            task_data["due_date"] = datetime.fromisoformat(task_data["due_date"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Format de date invalide (ISO 8601 attendu)")

    # Default : assigner a l'utilisateur courant si pas specifie
    if not task_data.get("assigned_to"):
        task_data["assigned_to"] = user.id

    task = Task(**task_data)
    db.add(task)
    await db.flush()
    await db.refresh(task)

    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Tache non trouvee")
    check_entity_access(task, user, owner_field="assigned_to")

    return _task_to_response(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Tache non trouvee")
    check_entity_access(task, user, owner_field="assigned_to")

    update_data = data.model_dump(exclude_unset=True)

    # Convertir les FK string → UUID
    for key in ("assigned_to", "contact_id", "deal_id"):
        if key in update_data and update_data[key]:
            update_data[key] = _parse_uuid(update_data[key], key)

    # Convertir due_date string → datetime
    if "due_date" in update_data and update_data["due_date"]:
        try:
            update_data["due_date"] = datetime.fromisoformat(update_data["due_date"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Format de date invalide (ISO 8601 attendu)")

    for field, value in update_data.items():
        setattr(task, field, value)

    await db.flush()
    await db.refresh(task)
    return _task_to_response(task)


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def toggle_task_completion(
    task_id: uuid.UUID,
    data: TaskCompletionToggle,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Tache non trouvee")
    check_entity_access(task, user, owner_field="assigned_to")

    task.is_completed = data.is_completed
    task.completed_at = datetime.now(UTC) if data.is_completed else None

    await db.flush()
    await db.refresh(task)
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Tache non trouvee")
    check_entity_access(task, user, owner_field="assigned_to")

    await db.delete(task)
