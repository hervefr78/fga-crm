// =============================================================================
// FGA CRM - Types : Dashboard Stats
// =============================================================================

export interface DealsByStage {
  stage: string;
  count: number;
  total_amount: number;
}

export interface ActivityByType {
  type: string;
  count: number;
}

export interface DashboardStats {
  contacts_total: number;
  contacts_this_month: number;
  companies_total: number;
  deals_total: number;
  deals_pipeline_amount: number;
  deals_won_amount: number;
  deals_won_count: number;
  deals_lost_count: number;
  deals_by_stage: DealsByStage[];
  activities_by_type: ActivityByType[];
  activities_total_30d: number;
  tasks_total: number;
  tasks_completed: number;
  tasks_overdue: number;
  emails_sent_30d: number;
  // Revenus recurrents
  deals_mrr_won: number;
  deals_arr_won: number;
  deals_mrr_pipeline: number;
  deals_one_shot_won: number;
  // Funding multi-source (Phase B 2026-05) — optional, backend ajoutera prochainement
  recent_funding_count?: number;
  recent_funding_amount?: number;
}
