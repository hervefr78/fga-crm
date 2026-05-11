// =============================================================================
// FGA CRM - Tests utils/format (Phase B 2026-05 — formatAmountMillions)
// =============================================================================

import { describe, it, expect } from 'vitest';
import { formatAmountMillions } from './format';

describe('formatAmountMillions', () => {
  it('formate les millions avec une decimale', () => {
    expect(formatAmountMillions(8_000_000)).toBe('8.0 M€');
    expect(formatAmountMillions(1_500_000)).toBe('1.5 M€');
    expect(formatAmountMillions(12_300_000)).toBe('12.3 M€');
  });

  it('formate les milliers sans decimale en dessous d\'1M', () => {
    expect(formatAmountMillions(500_000)).toBe('500 k€');
    expect(formatAmountMillions(50_000)).toBe('50 k€');
    expect(formatAmountMillions(999_999)).toBe('1000 k€');  // arrondi
  });

  it('retourne "—" pour null/undefined/0', () => {
    expect(formatAmountMillions(null)).toBe('—');
    expect(formatAmountMillions(undefined)).toBe('—');
    expect(formatAmountMillions(0)).toBe('—');
  });

  it('retourne "—" pour les valeurs negatives ou non-finite (DC1)', () => {
    expect(formatAmountMillions(-1000)).toBe('—');
    expect(formatAmountMillions(NaN)).toBe('—');
    expect(formatAmountMillions(Infinity)).toBe('—');
  });

  it('borne de 1M (limite exacte affichee en millions)', () => {
    expect(formatAmountMillions(1_000_000)).toBe('1.0 M€');
  });
});
