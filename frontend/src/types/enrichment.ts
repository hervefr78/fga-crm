// =============================================================================
// FGA CRM - Types Enrichissement (feature Compass) — alignes DC10 sur le backend
// =============================================================================

export type EnrichmentMode = 'company' | 'batch' | 'icp';
export type EnrichmentJobStatus = 'queued' | 'running' | 'done' | 'failed';

export interface EnrichmentJobStats {
  companies?: number;
  people_found?: number;
  emails_found?: number;
  valid?: number;
  suppressed?: number;
  skipped_fresh?: number;
  errors?: number;
  credits_spent?: number;
}

// EnrichmentJobResponse
export interface EnrichmentJob {
  id: string;
  mode: string;
  status: EnrichmentJobStatus;
  stats_json: EnrichmentJobStats;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface IcpFilterInput {
  naf_codes: string[];
  only_active?: boolean;
  min_revenue_eur?: number | null;
  require_domain?: boolean;
  limit?: number;
}

export interface EnrichmentJobCreateInput {
  mode: EnrichmentMode;
  siren?: string;
  sirens?: string[];
  icp_filter?: IcpFilterInput;
}

export interface EnrichmentJobList {
  items: EnrichmentJob[];
  total: number;
  page: number;
  size: number;
}
