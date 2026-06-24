// =============================================================================
// FGA CRM - API GEO (Generative Engine Optimization)
// =============================================================================
// Toutes les fonctions retournent des donnees typees alignees sur les schemas
// backend (app/api/v1/geo.py). Instance `api` partagee (base /api/v1, JWT injecte).
// =============================================================================

import api from './http';
import type {
  GeoBrand, GeoPrompt, GeoDashboard, GeoGap, GeoAlert,
  GeoHealth, GeoRunTriggerResponse, GeoEngine,
} from '../types/geo';

// --- Brands ---
export const listGeoBrands = async (isOwned?: boolean): Promise<GeoBrand[]> => {
  const params: Record<string, unknown> = {};
  if (isOwned !== undefined) params.is_owned = isOwned;
  const r = await api.get('/geo/brands', { params });
  return r.data as GeoBrand[];
};

// --- Prompts ---
export const listGeoPrompts = async (brandId: string): Promise<GeoPrompt[]> => {
  const r = await api.get(`/geo/brands/${brandId}/prompts`);
  return r.data as GeoPrompt[];
};

// --- Dashboard ---
export const getGeoDashboard = async (
  brandId: string,
  engine: GeoEngine,
  dateFrom?: string,
  dateTo?: string,
): Promise<GeoDashboard> => {
  const params: Record<string, unknown> = { engine };
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;
  const r = await api.get(`/geo/brands/${brandId}/dashboard`, { params });
  return r.data as GeoDashboard;
};

// --- Gaps (P4) ---
export const getGeoGaps = async (
  brandId: string,
  engine: GeoEngine,
  days = 7,
): Promise<GeoGap[]> => {
  const r = await api.get(`/geo/brands/${brandId}/gaps`, { params: { engine, days } });
  return Array.isArray(r.data) ? (r.data as GeoGap[]) : [];
};

// --- Alerts (P3) ---
export const getGeoAlerts = async (brandId: string, engine?: GeoEngine): Promise<GeoAlert[]> => {
  const params: Record<string, unknown> = {};
  if (engine) params.engine = engine;
  const r = await api.get(`/geo/brands/${brandId}/alerts`, { params });
  return Array.isArray(r.data) ? (r.data as GeoAlert[]) : [];
};

// --- Health (P3 — admin only) ---
export const getGeoHealth = async (): Promise<GeoHealth[]> => {
  const r = await api.get('/geo/health');
  return Array.isArray(r.data) ? (r.data as GeoHealth[]) : [];
};

// --- Trigger run (admin only) ---
export const triggerGeoRun = async (payload: {
  brand_id: string;
  engine: GeoEngine;
  prompt_ids: string[];
  n_runs?: number;
  country?: string;
  language?: string;
}): Promise<GeoRunTriggerResponse> => {
  const r = await api.post('/geo/runs/trigger', payload);
  return r.data as GeoRunTriggerResponse;
};

// --- Trigger remeasure (P4 — admin only) ---
export const triggerGeoRemeasure = async (
  brandId: string,
  engine: GeoEngine,
  days = 7,
  nRuns = 3,
): Promise<GeoRunTriggerResponse> => {
  const r = await api.post(
    `/geo/brands/${brandId}/gaps/remeasure`,
    null,
    { params: { engine, days, n_runs: nRuns } },
  );
  return r.data as GeoRunTriggerResponse;
};
