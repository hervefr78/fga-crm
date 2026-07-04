// =============================================================================
// FGA CRM - Audit : constantes, helpers de couleur purs + types partages
// (extraits de AuditResultPanel.tsx)
// =============================================================================

// Seuils de score pour les couleurs
export const SCORE_THRESHOLDS = { good: 70, medium: 40 } as const;

export function scoreColor(score: number): string {
  if (score >= SCORE_THRESHOLDS.good) return 'text-emerald-600';
  if (score >= SCORE_THRESHOLDS.medium) return 'text-amber-600';
  return 'text-red-500';
}

export function scoreBgColor(score: number): string {
  if (score >= SCORE_THRESHOLDS.good) return 'bg-emerald-50';
  if (score >= SCORE_THRESHOLDS.medium) return 'bg-amber-50';
  return 'bg-red-50';
}

export function scoreBarColor(score: number): string {
  if (score >= SCORE_THRESHOLDS.good) return 'bg-emerald-500';
  if (score >= SCORE_THRESHOLDS.medium) return 'bg-amber-500';
  return 'bg-red-500';
}

// Seuils GEO (/100)
export function geoScoreColor(score: number): string {
  if (score >= 60) return 'text-emerald-600';
  if (score >= 40) return 'text-amber-600';
  return 'text-red-500';
}

export function geoBgColor(score: number): string {
  if (score >= 60) return 'bg-emerald-50';
  if (score >= 40) return 'bg-amber-50';
  return 'bg-red-50';
}

export function gradeColor(grade: string): string {
  if (grade === 'A') return 'text-emerald-600 bg-emerald-50';
  if (grade === 'B') return 'text-blue-600 bg-blue-50';
  if (grade === 'C') return 'text-amber-600 bg-amber-50';
  return 'text-red-600 bg-red-50';
}

// ---------------------------------------------------------------------------
// Type partage : axe du radar messaging (utilise par RadarChart + MessagingAuditView)
// ---------------------------------------------------------------------------

export interface RadarAxis {
  key: string;
  value: number;
  label_fr: string;
  label_en?: string;
}
