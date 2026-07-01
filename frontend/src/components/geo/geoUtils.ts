// =============================================================================
// FGA CRM - GEO : constantes + helpers purs (extraits de GEO.tsx)
// =============================================================================

import type { GeoEngine, GeoIntent, GeoMetricsDaily } from '../../types/geo';

/** slug derive du nom : minuscules, alphanumerique + tirets. */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export const GEO_INTENTS: { value: GeoIntent; label: string }[] = [
  { value: 'informationnel', label: 'Informationnel' },
  { value: 'comparatif', label: 'Comparatif' },
  { value: 'transactionnel', label: 'Transactionnel' },
];

// Moteurs presentes dans le selecteur (sous-ensemble collectable — cf backend P1/P2)
export const ENGINES: { value: GeoEngine; label: string }[] = [
  { value: 'perplexity', label: 'Perplexity' },
  { value: 'openai', label: 'ChatGPT' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'google_aio', label: 'Google AIO' },
];

export const PERIODS: { value: '7' | '30' | '90'; label: string }[] = [
  { value: '7', label: '7 jours' },
  { value: '30', label: '30 jours' },
  { value: '90', label: '90 jours' },
];

export const INTENT_COLORS: Record<string, string> = {
  informationnel: 'bg-blue-50 text-blue-700',
  comparatif: 'bg-orange-50 text-orange-700',
  transactionnel: 'bg-emerald-50 text-emerald-700',
};

export const INTENT_LABELS: Record<string, string> = {
  informationnel: 'Informationnel',
  comparatif: 'Comparatif',
  transactionnel: 'Transactionnel',
};

// Couleurs des courbes (charte : indigo + emeraude, pas de gradient)
export const COLOR_SOV = '#4f46e5';
export const COLOR_VISIBILITY = '#10b981';

/** Moyenne d'un champ numerique sur les metriques, en ignorant les null. */
export function avgMetric(
  metrics: GeoMetricsDaily[],
  key: 'visibility_rate' | 'sov' | 'sov_weighted' | 'sentiment_avg',
): number | null {
  const values = metrics
    .map((m) => m[key])
    .filter((v): v is number => typeof v === 'number');
  if (values.length === 0) return null;
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

/** Formate un taux (0-100) en "xx.x %" ou "—" si null. */
export function formatRate(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(1)} %`;
}

/** Convertit un sentiment moyen (-1..1) en label lisible, ou "—" si null. */
export function sentimentLabel(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (value > 0.2) return 'Positif';
  if (value < -0.2) return 'Negatif';
  return 'Neutre';
}

/** Extrait un message d'erreur lisible d'une erreur axios, avec fallback. */
export function extractError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = resp?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}
