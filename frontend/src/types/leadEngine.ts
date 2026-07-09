// =============================================================================
// FGA CRM - Types Lead Engine (Signal Inbox)
// =============================================================================
// Aligne sur backend app/schemas/lead_engine.py.
// Regle metier : mmf_gap = seul declencheur d'outreach ; funding_detected
// ne declenche qu'un audit du message (docs/LEAD_ENGINE_VISION.md §2.0).
// =============================================================================

export type LeadSignalType = 'funding_detected' | 'mmf_gap' | 'inbound_new';
export type LeadSignalStatus = 'new' | 'actioned' | 'ignored';
export type LeadActionKind = 'audit' | 'contacts' | 'qualify' | 'outreach';

export interface LeadSignalDraft {
  contact_id: string;
  contact_name: string;
  contact_email: string;
  subject: string;
  body: string;
  angle_rationale: string;
  generated_at: string;
  model?: string;
  prompt_version?: string;
}

export interface LeadSignalPayload {
  company_name?: string | null;
  startup_radar_id?: string | null;
  funding_date?: string | null;
  funding_amount?: number | null;
  funding_series?: string | null;
  audit_score?: number | null;
  // inbound_new (P3)
  contact_id?: string;
  contact_name?: string;
  contact_email?: string | null;
  lead_source?: string;
  action?: { kind: LeadActionKind; at: string; by: string };
  draft?: LeadSignalDraft;
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
  action_kind?: LeadActionKind;
}

export interface LeadScanResult {
  created: Record<string, number>;
}

export interface LeadDraftResult {
  signal_id: string;
  contact_id: string;
  contact_name: string;
  contact_email: string;
  subject: string;
  body: string;
  angle_rationale: string;
  generated_at: string;
  meta: { model?: string; prompt_version?: string };
}

export interface LeadQueueItem {
  signal: LeadSignal;
  contacts_with_email: number;
  has_draft: boolean;
}

export interface LeadQueueResult {
  items: LeadQueueItem[];
  total: number;
}

export interface PlayFunnel {
  detected: number;
  actioned: number;
  drafted: number;
  sent: number;
}

export interface LeadFunnelResult {
  p1_mmf_gap: PlayFunnel;
  p2_funding: PlayFunnel;
  p3_inbound: PlayFunnel;
  period_days: number;
}
