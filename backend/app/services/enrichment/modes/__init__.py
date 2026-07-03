# =============================================================================
# FGA CRM - Enrichissement : handlers de mode
# =============================================================================
"""Handlers des modes d'enrichissement (company/batch/icp et contacts).

Chaque handler traite une unite de travail (societe ou contact) et depend
uniquement de `_pipeline` (helpers partages). Les modes ne s'importent pas
entre eux (graphe acyclique)."""
