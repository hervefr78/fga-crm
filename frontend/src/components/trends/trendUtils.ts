// =============================================================================
// FGA CRM - Trends : constantes + helpers purs (extraits de Trends.tsx)
// =============================================================================

import type { ElementType } from 'react';
import { Minus, TrendingDown, TrendingUp } from 'lucide-react';

import type { MarketPulse, TrendMode, TrendTimeframe } from '../../types/trends';

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

export function extractError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = resp?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}
