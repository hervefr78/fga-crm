// =============================================================================
// FGA CRM - TypeScript Types (barrel)
// =============================================================================
// Point d'entree unique : re-exporte tous les sous-modules de types par domaine.
// Les consommateurs importent depuis '../types' / '@/types' sans changement.
// NB : draft.ts / enrichment.ts / geo.ts / trends.ts sont importes directement
// par leurs consommateurs (pas via ce barrel) — comportement historique preserve.

export * from './entities';
export * from './api';
export * from './forms';
export * from './constants';
export * from './email';
export * from './integrations';
export * from './mcp';
export * from './dashboard';
export * from './ai';
