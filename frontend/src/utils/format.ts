// =============================================================================
// FGA CRM - Helpers de formatage (DC8 - centralise)
// =============================================================================

/**
 * Formate un montant en EUR avec precision adaptee :
 * - >= 1M : "1.5 M €"
 * - >= 10k : "12 k €"
 * - >= 1k : "1.5 k €" (1 decimale pour eviter d'arrondir 1500 a 2 k)
 * - < 1k : valeur formatee Intl.NumberFormat
 *
 * Garde-fou DC1 : les valeurs invalides retombent sur 0.
 */
export function formatCurrency(amount: number | null | undefined): string {
  const value = typeof amount === 'number' && Number.isFinite(amount) ? amount : 0;
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1).replace('.0', '')} M €`;
  }
  if (value >= 10_000) {
    return `${(value / 1_000).toFixed(0)} k €`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1).replace('.0', '')} k €`;
  }
  return value.toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  });
}

/**
 * Retourne le dernier jour du mois au format ISO YYYY-MM-DD.
 *
 * @param yyyymm - Format "YYYY-MM" (ex: "2026-04")
 * @returns ISO date string (ex: "2026-04-30") ou null si format invalide
 */
export function lastDayOfMonth(yyyymm: string): string | null {
  // Format strict YYYY-MM (DC1 - input borne)
  const match = /^(\d{4})-(\d{2})$/.exec(yyyymm);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!Number.isFinite(year) || month < 1 || month > 12) return null;

  // new Date(year, month, 0) = dernier jour du mois precedent (mois est 1-indexe ici)
  const last = new Date(year, month, 0);
  const day = String(last.getDate()).padStart(2, '0');
  return `${year}-${String(month).padStart(2, '0')}-${day}`;
}

/**
 * Formate une date ISO YYYY-MM-DD en DD/MM/YYYY (FR).
 * Retourne le placeholder si la date est nulle ou invalide.
 */
export function formatDateFR(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return placeholder;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

/**
 * Formate un montant en euros en notation compacte "M€" ou "k€" (specifique
 * funding rounds — plus compact que formatCurrency pour les badges).
 *
 * @param amountEur - montant en euros (null/undefined/0/NaN -> '—')
 * @returns "8.0 M€", "500 k€", "—" si invalide
 */
export function formatAmountMillions(amountEur: number | null | undefined): string {
  if (typeof amountEur !== 'number' || !Number.isFinite(amountEur) || amountEur <= 0) {
    return '—';
  }
  const m = amountEur / 1_000_000;
  if (m >= 1) return `${m.toFixed(1)} M€`;
  return `${(amountEur / 1_000).toFixed(0)} k€`;
}
