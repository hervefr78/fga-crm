// =============================================================================
// FGA CRM - API Trends (signal de demande de marche)
// =============================================================================
// Fonctions typees alignees sur les routes backend (app/api/v1/trends.py).
// Instance `api` partagee (base /api/v1, JWT injecte).
// =============================================================================

import api from './http';
import type {
  TrendCategory, TrendJob, TrendReport, TrendReportCreateInput, TrendHealth,
} from '../types/trends';

// --- Categories ---
export const listTrendCategories = async (): Promise<TrendCategory[]> => {
  const r = await api.get('/trends/categories');
  return Array.isArray(r.data) ? (r.data as TrendCategory[]) : [];
};

// --- Creation de rapport (job) ---
export const createTrendReport = async (
  payload: TrendReportCreateInput,
): Promise<TrendJob> => {
  const r = await api.post('/trends/reports', payload);
  return r.data as TrendJob;
};

// --- Statut d'un job ---
export const getTrendJob = async (jobId: string): Promise<TrendJob> => {
  const r = await api.get(`/trends/jobs/${jobId}`);
  return r.data as TrendJob;
};

// --- Rapport d'un job ---
export const getTrendReport = async (jobId: string): Promise<TrendReport> => {
  const r = await api.get(`/trends/reports/${jobId}`);
  return r.data as TrendReport;
};

// --- Dernier rapport pour une categorie ---
export const getLatestTrendReport = async (
  categoryId: string,
  country = 'FR',
  language = 'fr',
): Promise<TrendReport> => {
  const r = await api.get('/trends/reports/latest', {
    params: { category_id: categoryId, country, language },
  });
  return r.data as TrendReport;
};

// --- Health (admin only) ---
export const getTrendHealth = async (): Promise<TrendHealth> => {
  const r = await api.get('/trends/health');
  return r.data as TrendHealth;
};
