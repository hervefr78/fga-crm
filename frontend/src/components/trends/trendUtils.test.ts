// =============================================================================
// FGA CRM - Tests trendUtils (detail d'un point de la serie)
// =============================================================================

import { describe, it, expect } from 'vitest';

import { buildPointDetail } from './trendUtils';

const SERIES = [
  { date: 'd1', value: 40 },
  { date: 'd2', value: 60 },
  { date: 'd3', value: 50 },
];
// values=[40,60,50] -> mean=50, max=60 (d2), min=40 (d1)

describe('buildPointDetail', () => {
  it('index hors bornes -> null', () => {
    expect(buildPointDetail(SERIES, -1)).toBeNull();
    expect(buildPointDetail(SERIES, 3)).toBeNull();
    expect(buildPointDetail([], 0)).toBeNull();
  });

  it('1er point : delta null, creux (== min)', () => {
    const d = buildPointDetail(SERIES, 0)!;
    expect(d.delta).toBeNull();
    expect(d.isTrough).toBe(true);
    expect(d.isPeak).toBe(false);
    expect(d.mean).toBe(50);
  });

  it('point haut : delta positif, pic (== max)', () => {
    const d = buildPointDetail(SERIES, 1)!;
    expect(d.delta).toBe(20);       // 60 - 40
    expect(d.isPeak).toBe(true);
    expect(d.isTrough).toBe(false);
  });

  it('point median : delta negatif, ni pic ni creux, sur la moyenne', () => {
    const d = buildPointDetail(SERIES, 2)!;
    expect(d.delta).toBe(-10);      // 50 - 60
    expect(d.isPeak).toBe(false);
    expect(d.isTrough).toBe(false);
    expect(d.value >= d.mean).toBe(true);  // 50 >= 50 -> au-dessus/egal
  });
});
