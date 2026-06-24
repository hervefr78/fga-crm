// =============================================================================
// FGA CRM - API Drafts à valider
// =============================================================================
// Proxy CRM vers compass-core (drafts generes par le MCP). Utilise l'instance
// `api` partagee (base /api/v1, JWT injecte, 401 gere globalement).

import api from './http';
import type { DraftReview, DraftBrand, DraftStatus } from '../types';

// Borne par defaut alignee sur le backend (max_age_hours=48).
const DEFAULT_MAX_AGE_HOURS = 48;

// Liste les drafts en attente de validation (status 'to-review').
// `brand` optionnel filtre par marque ; sinon toutes marques confondues.
export const listPendingDrafts = async (
  params?: { brand?: DraftBrand; maxAgeHours?: number },
): Promise<DraftReview[]> => {
  const query: Record<string, unknown> = {
    max_age_hours: params?.maxAgeHours ?? DEFAULT_MAX_AGE_HOURS,
  };
  if (params?.brand) query.brand = params.brand;

  const response = await api.get('/drafts-review/pending', { params: query });
  // Defensif : le endpoint renvoie un tableau ; on garde-fou si la forme change (DC2).
  return Array.isArray(response.data) ? (response.data as DraftReview[]) : [];
};

// Recupere un draft unique par son identifiant.
export const getDraft = async (id: string): Promise<DraftReview> => {
  const response = await api.get(`/drafts-review/${id}`);
  return response.data as DraftReview;
};

// Met a jour le statut d'un draft (approved / rejected / to-review).
export const updateDraftStatus = async (
  id: string,
  status: DraftStatus,
): Promise<DraftReview> => {
  const response = await api.patch(`/drafts-review/${id}/status`, { status });
  return response.data as DraftReview;
};

// Extrait le filename d'un header Content-Disposition.
// Gere `filename="..."` et `filename=...` ; retourne null si introuvable.
const parseContentDispositionFilename = (header: unknown): string | null => {
  if (typeof header !== 'string') return null;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return match ? decodeURIComponent(match[1].trim()) : null;
};

// Telecharge le CSV HeyReach des drafts APPROUVES pour la marque donnee.
// `brand` optionnel : si absent, le backend exporte toutes les marques.
// Renvoie le blob, le filename resolu (header > fallback) et le nombre de
// leads ignores (header X-Skipped-Count, fallback 0).
export const exportHeyReachCsv = async (
  brand?: DraftBrand,
): Promise<{ blob: Blob; filename: string; skipped: number }> => {
  const params: Record<string, unknown> = {};
  if (brand) params.brand = brand;

  const res = await api.get('/drafts-review/export.csv', {
    params,
    responseType: 'blob',
  });

  const filename =
    parseContentDispositionFilename(res.headers['content-disposition']) ??
    `heyreach_${brand ?? 'all'}.csv`;

  const rawSkipped = Number(res.headers['x-skipped-count']);
  const skipped = Number.isFinite(rawSkipped) && rawSkipped > 0 ? rawSkipped : 0;

  return { blob: res.data as Blob, filename, skipped };
};
