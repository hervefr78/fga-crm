# =============================================================================
# FGA CRM - Schemas Task
# =============================================================================


from pydantic import BaseModel, Field, field_validator

# Valeurs autorisees (DC1 — validation contre Set)
TASK_TYPES = {"todo", "call", "email", "meeting"}
TASK_PRIORITIES = {"low", "medium", "high", "urgent"}


class TaskCreate(BaseModel):
    """Schema de creation d'une tache — tous les strings bornes (DC1)."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=5000)
    type: str = Field("todo", max_length=50)
    priority: str = Field("medium", max_length=20)
    due_date: str | None = Field(None, max_length=30)
    assigned_to: str | None = Field(None, max_length=36)
    contact_id: str | None = Field(None, max_length=36)
    deal_id: str | None = Field(None, max_length=36)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in TASK_TYPES:
            raise ValueError(
                f"Type invalide. Valeurs autorisees : {', '.join(sorted(TASK_TYPES))}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in TASK_PRIORITIES:
            raise ValueError(
                f"Priorite invalide. Valeurs autorisees : {', '.join(sorted(TASK_PRIORITIES))}"
            )
        return v


class TaskUpdate(BaseModel):
    """Schema de mise a jour partielle d'une tache."""

    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=5000)
    type: str | None = Field(None, max_length=50)
    priority: str | None = Field(None, max_length=20)
    due_date: str | None = Field(None, max_length=30)
    assigned_to: str | None = Field(None, max_length=36)
    contact_id: str | None = Field(None, max_length=36)
    deal_id: str | None = Field(None, max_length=36)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in TASK_TYPES:
            raise ValueError(
                f"Type invalide. Valeurs autorisees : {', '.join(sorted(TASK_TYPES))}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in TASK_PRIORITIES:
            raise ValueError(
                f"Priorite invalide. Valeurs autorisees : {', '.join(sorted(TASK_PRIORITIES))}"
            )
        return v


class TaskCompletionToggle(BaseModel):
    """Schema pour basculer l'etat de completion d'une tache."""

    is_completed: bool


class TaskResponse(BaseModel):
    """Schema de reponse pour une tache."""

    id: str
    title: str
    description: str | None
    type: str
    priority: str
    is_completed: bool
    due_date: str | None
    completed_at: str | None
    assigned_to: str | None
    contact_id: str | None
    deal_id: str | None
    created_at: str

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Schema de reponse paginee pour les taches."""

    items: list[TaskResponse]
    total: int
    page: int
    size: int
    pages: int
