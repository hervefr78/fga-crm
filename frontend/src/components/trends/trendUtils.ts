// =============================================================================
// FGA CRM - Trends : constantes + helpers purs (extraits de Trends.tsx)
// =============================================================================

import type { ElementType } from 'react';
import { Minus, TrendingDown, TrendingUp } from 'lucide-react';

import type { MarketPulse, TrendMode, TrendObjective, TrendTimeframe } from '../../types/trends';

export const JOB_POLL_INTERVAL = 2000; // ms — polling d'un job deep en cours

export const TIMEFRAMES: { value: TrendTimeframe; label: string }[] = [
  { value: 'now 7-d', label: '7 jours' },
  { value: 'today 1-m', label: '1 mois' },
  { value: 'today 3-m', label: '3 mois' },
  { value: 'today 12-m', label: '12 mois' },
  { value: 'today 5-y', label: '5 ans' },
];

export const MODES: { value: TrendMode; label: string }[] = [
  { value: 'quick', label: 'Rapide' },
  { value: 'deep', label: 'Profonde' },
];

// Objectif d'exploitation (mode Profond) : oriente les recommandations LLM.
export const OBJECTIVES: { value: TrendObjective; label: string }[] = [
  { value: 'content', label: 'Contenu' },
  { value: 'seo', label: 'SEO' },
  { value: 'ads', label: 'Ads' },
  { value: 'prospection', label: 'Prospection' },
];

export const COUNTRIES: { value: string; label: string }[] = [
  { value: 'FR', label: 'France' },
  { value: 'BE', label: 'Belgique' },
  { value: 'CH', label: 'Suisse' },
  { value: 'CA', label: 'Canada' },
];

export const DIRECTION_META: Record<
  MarketPulse['direction'],
  { label: string; icon: ElementType; color: string }
> = {
  up: { label: 'En hausse', icon: TrendingUp, color: 'text-emerald-600' },
  down: { label: 'En baisse', icon: TrendingDown, color: 'text-red-500' },
  flat: { label: 'Stable', icon: Minus, color: 'text-slate-400' },
};

export function formatScore(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toFixed(1);
}

export function formatGrowth(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `+${value.toFixed(0)} %`;
}

// Detail derive d'un point de la serie temporelle (aucune donnee par point cote
// provider : on calcule le contexte a partir de la serie elle-meme).
export interface TrendPointDetail {
  date: string;
  value: number;
  delta: number | null;   // variation vs point precedent (null au 1er point)
  isPeak: boolean;        // point le plus haut de la periode
  isTrough: boolean;      // point le plus bas de la periode
  mean: number;           // moyenne de la serie (arrondie)
}

export function buildPointDetail(
  series: { date: string; value: number }[],
  index: number,
): TrendPointDetail | null {
  if (index < 0 || index >= series.length) return null;
  const values = series.map((p) => p.value);
  const mean = Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  const pt = series[index];
  const prev = index > 0 ? series[index - 1] : null;
  return {
    date: pt.date,
    value: pt.value,
    delta: prev ? pt.value - prev.value : null,
    isPeak: pt.value === Math.max(...values),
    isTrough: pt.value === Math.min(...values),
    mean,
  };
}

export function extractError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = resp?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}
