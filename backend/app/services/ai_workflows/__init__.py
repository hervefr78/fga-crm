# =============================================================================
# FGA CRM - Workflows IA natifs (scoring, qualification, insights)
# =============================================================================
"""Workflows IA executes cote backend (spec workflows-ia) : le CRM declenche,
le CRM stocke, le CRM affiche. Stack LLM unique : OpenAI structured outputs
(pattern partage services/openai_strict.py — sortie JSON stricte validee
Pydantic, jamais de parsing texte fragile).

Modules :
- client.py  : appel LLM commun (retry, erreurs typees)
- runs.py    : journal d'audit ai_workflow_runs (org-scope, tokens, statut)
- scoring.py : Workflow 1 — scoring des deals (fit + intent + opportunite message)
"""
