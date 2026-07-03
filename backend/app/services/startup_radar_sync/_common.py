# =============================================================================
# FGA CRM - Startup Radar Sync : helpers communs
# SyncResult + parsing/formatage + fusion des resultats partiels
# =============================================================================

from dataclasses import dataclass, field
from datetime import date


@dataclass
class SyncResult:
    """Resultat d'une synchronisation SR → CRM."""

    companies_created: int = 0
    companies_updated: int = 0
    contacts_created: int = 0
    contacts_updated: int = 0
    investors_created: int = 0
    investors_updated: int = 0
    audits_created: int = 0
    # Funding multi-source (Phase B 2026-05)
    funding_activities_created: int = 0
    qualification_tasks_created: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers funding (Phase B 2026-05)
# ---------------------------------------------------------------------------


def _parse_iso_date(value: str | None) -> date | None:
    """Convertir une chaine ISO YYYY-MM-DD en date, ou None si invalide.

    Tolere None et string vide (retour None sans erreur). Utilise pour les
    champs funding_date qui peuvent etre absents/mal formes dans la reponse SR.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _format_amount_subject(amount_eur: int, series: str | None) -> str:
    """Sujet stable pour Activity 'funding_detected' (cle d'idempotence).

    Inclut le montant en M€ et la serie pour permettre des rounds successifs
    sur la meme company (Seed → Serie A → Serie B = 3 activities distinctes).
    """
    amount_m = amount_eur / 1_000_000
    series_label = series or "Levée"
    return f"Levée détectée : {amount_m:.1f}M€ ({series_label})"


def _merge_results(total: SyncResult, partial: SyncResult) -> None:
    """Fusionner un resultat partiel dans le total."""
    total.companies_created += partial.companies_created
    total.companies_updated += partial.companies_updated
    total.contacts_created += partial.contacts_created
    total.contacts_updated += partial.contacts_updated
    total.investors_created += partial.investors_created
    total.investors_updated += partial.investors_updated
    total.audits_created += partial.audits_created
    total.funding_activities_created += partial.funding_activities_created
    total.qualification_tasks_created += partial.qualification_tasks_created
    total.errors.extend(partial.errors)
