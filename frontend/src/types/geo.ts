// =============================================================================
// FGA CRM - Types GEO (Generative Engine Optimization)
// =============================================================================
// Types alignes EXACTEMENT sur les schemas backend (app/schemas/geo.py) — DC10.
// Toute divergence de nom de champ = source de bug silencieux cote front.
// =============================================================================

export type GeoEngine = 'perplexity' | 'openai' | 'gemini' | 'claude' | 'grok' | 'google_aio';
export type GeoIntent = 'informationnel' | 'comparatif' | 'transactionnel';
export type GeoSentiment = 'positif' | 'neutre' | 'negatif';

// GeoBrandResponse
export interface GeoBrand {
  id: string;
  slug: string;
  name: string;
  aliases: string[];
  is_owned: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
}

// GeoPromptResponse — note : intent renvoye en str par le backend
export interface GeoPrompt {
  id: string;
  brand_id: string;
  text: string;
  intent: GeoIntent;
  persona: string | null;
  country: string;
  language: string;
  tags: string[];
  priority: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
}

// GeoBrandOverviewResponse — marque + visibilite moyenne (selecteur avec mini-score)
export interface GeoBrandOverview {
  id: string;
  slug: string;
  name: string;
  visibility_rate: number | null;
}

// Payloads de creation (alignes sur GeoBrandCreate / GeoPromptCreate backend)
export interface GeoBrandInput {
  slug: string;
  name: string;
  aliases: string[];
  is_owned: boolean;
  active?: boolean;
}

export interface GeoPromptInput {
  text: string;
  intent: GeoIntent;
  persona?: string | null;
  country?: string;
  language?: string;
  tags?: string[];
  priority?: boolean;
  active?: boolean;
}

// GeoRunResponse — backend expose raw_answer + created_at (cf schemas/geo.py)
export interface GeoRun {
  id: string;
  prompt_id: string;
  brand_id: string;
  run_index: number;
  engine: GeoEngine;
  model_version: string | null;
  country: string | null;
  language: string | null;
  run_at: string;
  raw_answer: string | null;
  citations: Array<{ url: string; domain: string; rank: number }>;
  brands_found: Array<{ nom: string; rang: number; recommandee: boolean; sentiment: GeoSentiment }>;
  brand_mentioned: boolean | null;
  brand_position: number | null;
  brand_sentiment: GeoSentiment | null;
  brand_recommended: boolean | null;
  appearance: boolean | null;
  created_at: string;
}

// GeoMetricsDailyResponse — backend expose computed_at en plus
export interface GeoMetricsDaily {
  id: string;
  day: string;
  brand_id: string;
  engine: GeoEngine;
  visibility_rate: number | null;
  sov: number | null;
  sov_weighted: number | null;
  sentiment_avg: number | null;
  reco_rate: number | null;
  runs_total: number;
  computed_at: string;
}

// GeoDashboardResponse
export interface GeoDashboard {
  brand: GeoBrand;
  engine: string;
  date_from: string;
  date_to: string;
  metrics: GeoMetricsDaily[];
  top_competitors: Array<{ nom: string; mentions: number; sov_share: number }>;
  top_sources: Array<{ domain: string; count: number }>;
}

// Reponse de GET /brands/{id}/gaps (dicts bruts cote backend — pas de schema Pydantic)
export interface GeoGap {
  prompt_id: string;
  prompt_text: string;
  intent: GeoIntent;
  priority: boolean;
  runs_checked: number;
  mentions: number;
  visibility_rate: number;
  top_competitor_sources: Array<{ domain: string; count: number }>;
  top_competitors: Array<{ nom: string; count: number }>;
  last_run_at: string | null;
  action_suggestion: string;
}

// Reponse de GET /brands/{id}/alerts (dicts bruts cote backend)
export interface GeoAlert {
  alert_type: 'sov_drop' | 'visibility_zero' | 'sentiment_negative' | 'competitor_overtake';
  engine: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  detail: Record<string, unknown>;
  detected_at: string;
}

// GeoHealthResponse
export interface GeoHealth {
  engine: string;
  status: 'ok' | 'error' | 'unconfigured';
  checked_at: string;
  error: string | null;
}

// GeoRunTriggerResponse
export interface GeoRunTriggerResponse {
  task_id: string;
  runs_scheduled: number;
}

// GeoRunListResponse
export interface GeoRunsPage {
  items: GeoRun[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
