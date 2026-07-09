// =============================================================================
// FGA CRM - Lead Engine : helpers purs (libelles, dates relatives)
// =============================================================================

import { formatAmountMillions, formatDateFR } from '../../utils/format';
import type { LeadSignal } from '../../types/leadEngine';

export const SIGNAL_TYPE_LABELS: Record<string, string> = {
  funding_detected: 'Levée détectée',
  mmf_gap: 'MMF gap',
};

export const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau',
  actioned: 'Traité',
  ignored: 'Ignoré',
};

export const STATUS_BADGES: Record<string, string> = {
  new: 'bg-primary-50 text-primary-700',
  actioned: 'bg-emerald-50 text-emerald-700',
  ignored: 'bg-slate-100 text-slate-500',
};

/** Date relative compacte ("il y a 3 j", "hier", sinon date FR). */
export function timeAgo(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days <= 0) return "aujourd'hui";
  if (days === 1) return 'hier';
  if (days < 30) return `il y a ${days} j`;
  return formatDateFR(iso);
}

/** Qualificateur de solvabilite ("levée 4.5 M€ (Série A) il y a 12 j").
 *  Montant inconnu (0 en base, frequent cote SR) -> omis plutot que "levée —". */
export function fundingQualifier(signal: LeadSignal): string | null {
  const p = signal.payload_json;
  if (!p.funding_amount && !p.funding_date) return null;
  const parts = ['levée'];
  if (p.funding_amount) parts.push(formatAmountMillions(p.funding_amount));
  if (p.funding_series) parts.push(`(${p.funding_series})`);
  if (p.funding_date) parts.push(timeAgo(p.funding_date));
  return parts.join(' ');
}

/** Raison du signal, affichee en premier — c'est le gap qu'on vend. */
export function signalReason(signal: LeadSignal): string {
  const p = signal.payload_json;
  if (signal.signal_type === 'mmf_gap') {
    const score = typeof p.audit_score === 'number' ? `${p.audit_score}/75` : 'sous le seuil';
    return `Message flou mesuré : audit ${score}`;
  }
  return fundingQualifier(signal) ?? 'Levée récente';
}
