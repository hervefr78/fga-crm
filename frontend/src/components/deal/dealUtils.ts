// =============================================================================
// FGA CRM - Utils & constantes de la fiche Deal
// Constantes (pipeline stages, badge maps, activity icons) + helpers de format.
// Extrait de DealDetail.tsx (refactor C5) — logique inchangee.
// =============================================================================

import type { ElementType } from 'react';
import { Mail, Phone, Linkedin, FileText, Video, Check } from 'lucide-react';

import { DEAL_PRICING_TYPES } from '../../types';

// -----------------------------------------------------------------------------
// Constantes
// -----------------------------------------------------------------------------

export const SPLIT_VIEW_SIZE = 200;

export const PIPELINE_STAGES = [
  { key: 'new', label: 'Nouveau' },
  { key: 'contacted', label: 'Contacte' },
  { key: 'meeting', label: 'Meeting' },
  { key: 'proposal', label: 'Proposition' },
  { key: 'negotiation', label: 'Negociation' },
  { key: 'won', label: 'Gagne' },
];

export const STAGE_LABELS: Record<string, string> = Object.fromEntries(
  PIPELINE_STAGES.map((s) => [s.key, s.label]),
);
STAGE_LABELS.lost = 'Perdu';

export const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-blue-50 text-blue-700',
  high: 'bg-amber-50 text-amber-700',
  urgent: 'bg-red-50 text-red-600',
};
export const PRIORITY_LABELS: Record<string, string> = {
  low: 'Basse', medium: 'Moyenne', high: 'Haute', urgent: 'Urgente',
};

export const PRICING_LABELS: Record<string, string> = Object.fromEntries(
  DEAL_PRICING_TYPES.map((p) => [p.value, p.label]),
);

export const PRICING_PERIOD_LABEL: Record<string, string> = {
  monthly: 'mensuel',
  quarterly: 'trimestriel',
  biannual: 'semestriel',
  annual: 'annuel',
};

export const ACTIVITY_ICONS: Record<string, ElementType> = {
  email: Mail, call: Phone, meeting: Video, note: FileText,
  linkedin: Linkedin, task: Check,
};
export const ACTIVITY_BG: Record<string, string> = {
  email: 'bg-blue-50 text-blue-600',
  call: 'bg-emerald-50 text-emerald-600',
  meeting: 'bg-indigo-50 text-indigo-600',
  note: 'bg-amber-50 text-amber-600',
  linkedin: 'bg-sky-50 text-sky-600',
  task: 'bg-slate-100 text-slate-600',
};

// -----------------------------------------------------------------------------
// Helpers de format
// -----------------------------------------------------------------------------

export function formatDate(d?: string | null) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
}
export function formatTime(d?: string | null) {
  if (!d) return '';
  return new Date(d).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}
export function formatDay(d?: string | null) {
  if (!d) return '';
  const date = new Date(d);
  const today = new Date();
  const yesterday = new Date(); yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Aujourd'hui";
  if (date.toDateString() === yesterday.toDateString()) return 'Hier';
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
}
