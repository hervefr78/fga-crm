// =============================================================================
// FGA CRM - Types : Integrations (Startup Radar sync, audits)
// =============================================================================

export interface SyncResult {
  companies_created: number;
  companies_updated: number;
  contacts_created: number;
  contacts_updated: number;
  investors_created: number;
  investors_updated: number;
  audits_created: number;
  // Funding multi-source (Phase B 2026-05)
  funding_activities_created?: number;
  qualification_tasks_created?: number;
  errors: string[];
}

export type SyncJobStatus = 'idle' | 'running' | 'completed' | 'failed';

export interface SyncStatus {
  has_synced: boolean;
  status: SyncJobStatus;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  last_result: SyncResult | null;
}

// Reponse 202 du lancement d'une full sync (tache de fond)
export interface SyncEnqueued {
  status: string;
  job_id: string;
  started_at: string;
}

export interface CompanyAuditResponse {
  audits_created: number;
  audits_skipped: number;
  errors: string[];
}

// Statut de generation d'un audit SR a la demande (proxy du statut SR)
export interface AuditGenerateStatus {
  status: 'idle' | 'running' | 'completed' | 'failed';
  step: string;
  error: string | null;
}
