// =============================================================================
// FGA CRM - Company : constantes + helpers purs (extraits de CompanyDetail.tsx)
// =============================================================================

import type { ElementType } from 'react';
import {
  Mail, Phone, Video, FileText, Linkedin, Check, Zap,
} from 'lucide-react';

// Pagination split-view : 200 items pour couvrir les volumes type 1500+ contacts
// (DC1 — borne raisonnable, le backend cap a 100 par defaut mais accepte 200).
export const SPLIT_VIEW_SIZE = 200;

export const STAGE_LABELS: Record<string, string> = {
  new: 'Nouveau', contacted: 'Contacte', meeting: 'Meeting',
  proposal: 'Proposition', negotiation: 'Negociation',
  won: 'Gagne', lost: 'Perdu',
};

export const STAGE_COLORS: Record<string, string> = {
  new: 'bg-slate-100 text-slate-600',
  contacted: 'bg-blue-50 text-blue-700',
  meeting: 'bg-indigo-50 text-indigo-700',
  proposal: 'bg-amber-50 text-amber-700',
  negotiation: 'bg-orange-50 text-orange-700',
  won: 'bg-emerald-50 text-emerald-700',
  lost: 'bg-red-50 text-red-600',
};

export const ACTIVITY_ICONS: Record<string, ElementType> = {
  email: Mail, call: Phone, meeting: Video, note: FileText,
  linkedin: Linkedin, task: Check, audit: Zap,
};

export const ACTIVITY_BG: Record<string, string> = {
  email: 'bg-blue-50 text-blue-600',
  call: 'bg-emerald-50 text-emerald-600',
  meeting: 'bg-indigo-50 text-indigo-600',
  note: 'bg-amber-50 text-amber-600',
  linkedin: 'bg-sky-50 text-sky-600',
  task: 'bg-slate-100 text-slate-600',
  audit: 'bg-violet-50 text-violet-600',
};

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

export function cleanUrl(url: string) {
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

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

export function formatRelative(d?: string | null) {
  if (!d) return '—';
  const diff = Date.now() - new Date(d).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "aujourd'hui";
  if (days === 1) return 'hier';
  if (days < 30) return `il y a ${days} j`;
  return formatDate(d);
}
