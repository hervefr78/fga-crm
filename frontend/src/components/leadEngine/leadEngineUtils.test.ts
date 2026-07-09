// =============================================================================
// FGA CRM - Tests des helpers Lead Engine (dates relatives, libelles)
// =============================================================================

import { describe, it, expect } from 'vitest';

import type { LeadSignal } from '../../types/leadEngine';
import { fundingQualifier, signalReason, timeAgo } from './leadEngineUtils';

const DAY_MS = 86_400_000;

function signal(overrides: Partial<LeadSignal> = {}): LeadSignal {
  return {
    id: 's1', signal_type: 'mmf_gap', status: 'new', company_id: 'c1',
    payload_json: {}, created_at: '2026-07-09T10:00:00Z', updated_at: '2026-07-09T10:00:00Z',
    ...overrides,
  };
}

describe('timeAgo', () => {
  it('gere aujourd\'hui / hier / N jours', () => {
    expect(timeAgo(new Date().toISOString())).toBe("aujourd'hui");
    expect(timeAgo(new Date(Date.now() - DAY_MS).toISOString())).toBe('hier');
    expect(timeAgo(new Date(Date.now() - 12 * DAY_MS).toISOString())).toBe('il y a 12 j');
  });

  it('bascule en date FR au-dela de 30 jours', () => {
    const old = new Date(Date.now() - 60 * DAY_MS).toISOString();
    expect(timeAgo(old)).toMatch(/^\d{2}\/\d{2}\/\d{4}$/);
  });

  it('renvoie un placeholder sur date invalide', () => {
    expect(timeAgo('pas-une-date')).toBe('—');
    expect(timeAgo('')).toBe('—');
  });
});

describe('fundingQualifier', () => {
  it('assemble montant + serie + recence', () => {
    const s = signal({
      payload_json: {
        funding_amount: 4_500_000, funding_series: 'Série A',
        funding_date: new Date(Date.now() - 12 * DAY_MS).toISOString().slice(0, 10),
      },
    });
    expect(fundingQualifier(s)).toBe('levée 4.5 M€ (Série A) il y a 12 j');
  });

  it('renvoie null sans donnee de levee', () => {
    expect(fundingQualifier(signal())).toBeNull();
  });

  it('montant inconnu (0) : omis plutot que "levée —"', () => {
    const s = signal({
      payload_json: {
        funding_amount: 0,
        funding_date: new Date(Date.now() - 5 * DAY_MS).toISOString().slice(0, 10),
      },
    });
    expect(fundingQualifier(s)).toBe('levée il y a 5 j');
  });
});

describe('signalReason', () => {
  it('mmf_gap : affiche le score mesure /75', () => {
    const s = signal({ payload_json: { audit_score: 24 } });
    expect(signalReason(s)).toBe('Message flou mesuré : audit 24/75');
  });

  it('mmf_gap sans score : reste explicite sans inventer de chiffre', () => {
    expect(signalReason(signal())).toBe('Message flou mesuré : audit sous le seuil');
  });

  it('funding_detected : la raison est la levee', () => {
    const s = signal({
      signal_type: 'funding_detected',
      payload_json: { funding_amount: 500_000 },
    });
    expect(signalReason(s)).toBe('levée 500 k€');
  });

  it('funding_detected sans montant : libelle generique', () => {
    const s = signal({ signal_type: 'funding_detected' });
    expect(signalReason(s)).toBe('Levée récente');
  });
});
