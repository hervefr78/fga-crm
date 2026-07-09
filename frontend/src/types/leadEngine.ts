// =============================================================================
// FGA CRM - Types Lead Engine (Signal Inbox)
// =============================================================================
// Aligne sur backend app/schemas/lead_engine.py.
// Regle metier : mmf_gap = seul declencheur d'outreach ; funding_detected
// ne declenche qu'un audit du message (docs/LEAD_ENGINE_VISION.md §2.0).
// =============================================================================

export type LeadSignalType = 'funding_detected' | 'mmf_gap';
export type LeadSignalStatus = 'new' | 'actioned' | 'ignored';

export interface LeadSignalPayload {
  company_name?: string;
  startup_radar_id?: string | null;
  funding_date?: string | null;
  funding_amount?: number | null;
  funding_series?: string | null;
  audit_score?: number | null;
  action?: { kind: 'audit' | 'contacts'; at: string; by: string };
}

export interface LeadSignal {
  id: string;
  signal_type: LeadSignalType;
  status: LeadSignalStatus;
  company_id: string | null;
  payload_json: LeadSignalPayload;
  created_at: string;
  updated_at: string;
}

export interface LeadSignalStats {
  new_total: number;
  new_funding: number;
  new_mmf: number;
  actioned_7d: number;
  ignored_7d: number;
}

export interface LeadSignalList {
  items: LeadSignal[];
  total: number;
  page: number;
  size: number;
  stats: LeadSignalStats;
}

export interface LeadSignalUpdateInput {
  status: LeadSignalStatus;
  action_kind?: 'audit' | 'contacts';
}

export interface LeadScanResult {
  created: Record<string, number>;
}
