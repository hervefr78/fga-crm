# =============================================================================
# FGA CRM - Dashboard Schemas (stats agregees)
# =============================================================================

from pydantic import BaseModel, Field


class DealsByStage(BaseModel):
    """Nombre de deals et montant total par stage."""

    stage: str
    count: int = 0
    total_amount: float = 0.0


class ActivityByType(BaseModel):
    """Nombre d'activites par type (30 derniers jours)."""

    type: str
    count: int = 0


class DashboardStats(BaseModel):
    """Statistiques agregees pour le dashboard."""

    # Compteurs principaux
    contacts_total: int = Field(0, description="Total contacts")
    contacts_this_month: int = Field(0, description="Contacts crees ce mois")
    companies_total: int = Field(0, description="Total entreprises")
    deals_total: int = Field(0, description="Total deals")
    deals_pipeline_amount: float = Field(0.0, description="Montant pipeline (hors won/lost)")
    deals_won_amount: float = Field(0.0, description="Revenue gagnee (stage=won)")
    deals_won_count: int = Field(0, description="Nombre deals gagnes")
    deals_lost_count: int = Field(0, description="Nombre deals perdus")

    # Pipeline par stage (pour bar chart)
    deals_by_stage: list[DealsByStage] = Field(default_factory=list)

    # Activites par type (30 derniers jours, pour pie chart)
    activities_by_type: list[ActivityByType] = Field(default_factory=list)
    activities_total_30d: int = Field(0, description="Total activites 30 derniers jours")

    # Taches
    tasks_total: int = Field(0, description="Total taches")
    tasks_completed: int = Field(0, description="Taches completees")
    tasks_overdue: int = Field(0, description="Taches en retard")

    # Emails
    emails_sent_30d: int = Field(0, description="Emails envoyes 30 derniers jours")
