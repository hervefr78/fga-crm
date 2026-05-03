# ADR-004 : Sync one-way Startup Radar → CRM

## Date
2026-02-22

## Statut
accepted

## Contexte
Le CRM doit importer des donnees depuis Startup Radar (startups, investors, contacts, audits). La question est le sens de synchronisation et la strategie de dedup.

## Decision
Sync one-way SR → CRM uniquement. Deduplication via champ `startup_radar_id` (unique) sur Company et Contact. Mapping :
- startups → Companies
- investors → Companies (id prefixe `inv:`, industry = Capital-risque)
- contacts → Contacts
- audits → Activity(type=audit)

Auth SR via JWT (email/password login, pas API key).

## Alternatives envisagees
- Sync bidirectionnelle — rejetee parce que le CRM est le systeme maitre, pas besoin de pousser vers SR
- Import CSV depuis SR — rejetee parce que SR a une API REST, plus fiable et automatisable
- Webhook push depuis SR — rejetee parce que SR ne supporte pas les webhooks

## Consequences
- Chaque Company/Contact peut avoir un `startup_radar_id` nullable
- L'endpoint sync est idempotent (re-run safe grace a la dedup)
- Les audits sont dedupliques par `(company_id, type, subject)`
- Les erreurs dans une iteration n'empoisonnent pas la transaction (savepoints `begin_nested()`)

## Fichiers impactes
- `backend/app/services/startup_radar.py` — client API SR
- `backend/app/services/startup_radar_sync.py` — logique de sync
- `backend/app/api/v1/integrations.py` — endpoint sync + audit
- `backend/app/models/company.py`, `contact.py` — champ `startup_radar_id`
