// =============================================================================
// FGA CRM - Types Trends (signal de demande de marche)
// =============================================================================
// Alignes EXACTEMENT sur les schemas backend (app/schemas/trends.py) — DC10.
// =============================================================================

export type TrendMode = 'quick' | 'deep';

export type TrendObjective = 'seo' | 'ads' | 'content' | 'prospection';

export type TrendTimeframe =
  | 'now 7-d'
  | 'today 1-m'
  | 'today 3-m'
  | 'today 12-m'
  | 'today 5-y';

export type TrendJobStatusValue = 'queued' | 'running' | 'completed' | 'failed';

// TrendCategoryResponse
export interface TrendCategory {
  id: string;
  slug: string;
  label: string;
  provider: string;
  provider_category_id: string | null;
  parent_slug: string | null;
  active: boolean;
  display_order: number;
}

// TrendReportCreateRequest
// Ciblage : `category_id` (categorie du referentiel) OU `query` (sujet libre,
// analyse one-shot). Exactement un des deux — valide cote backend.
export interface TrendReportCreateInput {
  mode: TrendMode;
  category_id?: string;
  query?: string;
  country?: string;
  language?: string;
  timeframe?: TrendTimeframe;
  seed_terms?: string[];
  objective?: TrendObjective;
  refresh?: boolean;
}

export interface TrendJobProgress {
  steps_total: number;
  steps_done: number;
}

// TrendJobResponse
export interface TrendJob {
  job_id: string;
  mode: string;
  status: TrendJobStatusValue;
  provider_primary: string;
  provider_effective: string | null;
  cache_hit: boolean;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  progress: TrendJobProgress;
  created_at: string;
}

// Signaux normalises
export interface MarketPulse {
  interest_index: number;
  direction: 'up' | 'down' | 'flat';
  freshness: 'fresh' | 'cached';
}

export interface TrendQuery {
  query: string;
  value: number;
  growth: number | null;
  breakout: boolean;
}

export interface TrendTopic {
  topic: string;
  value: number;
}

export interface TrendRegion {
  region: string;
  value: number;
}

export interface TrendTimeseriesPoint {
  date: string;
  value: number;
}

export interface TrendSignals {
  market_pulse: MarketPulse;
  timeseries: TrendTimeseriesPoint[];
  rising_queries: TrendQuery[];
  top_queries: TrendQuery[];
  related_topics: TrendTopic[];
  regions: TrendRegion[];
}

export interface TrendReportMeta {
  provider_effective: string;
  generated_at: string;
  cached: boolean;
  category_slug: string;
  country: string;
  language: string;
  timeframe: string;
}

// Recommandations LLM (mode Profond)
export interface TrendKeywordRec {
  keyword: string;
  cluster: string;
  rationale: string;
}

export interface TrendWatchQuery {
  query: string;
  reason: string;
}

export interface TrendRecommendations {
  strategy: string;
  objective: string | null;
  target_keywords: TrendKeywordRec[];
  watch_queries: TrendWatchQuery[];
  content_angles: string[];
}

// TrendReportResponse
export interface TrendReport {
  job_id: string;
  status: string;
  summary_md: string | null;
  opportunity_score: number | null;
  signals: TrendSignals | null;
  meta: TrendReportMeta | null;
  recommendations: TrendRecommendations | null;
}

// TrendReportListItem (historique des analyses)
export interface TrendReportListItem {
  job_id: string;
  mode: string;
  category_label: string;
  objective: string | null;
  country: string;
  timeframe: string;
  opportunity_score: number | null;
  created_at: string;
}

// TrendHealthResponse
export interface TrendHealth {
  provider: string;
  status: 'ok' | 'error' | 'unconfigured';
  latency_ms: number | null;
  error: string | null;
}
