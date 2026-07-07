// =============================================================================
// FGA CRM - Tests companiesListState (URL <-> etat de vue + persistance)
// =============================================================================

import { describe, it, expect, beforeEach } from 'vitest';

import {
  parseListParams, buildListParams, saveCompaniesListQuery, companiesListUrl,
} from './companiesListState';

const FILTER_KEYS = ['industry', 'lead_source', 'size_range'];

describe('parseListParams', () => {
  it('URL vide -> defauts', () => {
    const s = parseListParams(new URLSearchParams(), FILTER_KEYS);
    expect(s).toEqual({
      search: '', page: 1, sortBy: 'created_at', sortDir: 'desc', filters: {},
    });
  });

  it('lit recherche, page, tri et filtres', () => {
    const s = parseListParams(
      new URLSearchParams('q=bio&page=3&sort_by=funding_amount&sort_dir=asc&industry=Biotech&lead_source=startup_radar'),
      FILTER_KEYS,
    );
    expect(s.search).toBe('bio');
    expect(s.page).toBe(3);
    expect(s.sortBy).toBe('funding_amount');
    expect(s.sortDir).toBe('asc');
    expect(s.filters).toEqual({ industry: 'Biotech', lead_source: 'startup_radar' });
  });

  it('valeurs invalides -> defauts (DC1)', () => {
    const s = parseListParams(
      new URLSearchParams('page=abc&sort_by=DROP&sort_dir=up'),
      FILTER_KEYS,
    );
    expect(s.page).toBe(1);
    expect(s.sortBy).toBe('created_at');
    expect(s.sortDir).toBe('desc');
  });

  it('page 0 / negative -> 1', () => {
    expect(parseListParams(new URLSearchParams('page=0'), FILTER_KEYS).page).toBe(1);
    expect(parseListParams(new URLSearchParams('page=-4'), FILTER_KEYS).page).toBe(1);
  });
});

describe('buildListParams', () => {
  it('omet les defauts (URL propre)', () => {
    const params = buildListParams(
      { search: '', page: 1, sortBy: 'created_at', sortDir: 'desc', filters: {} },
      FILTER_KEYS,
    );
    expect(params.toString()).toBe('');
  });

  it('roundtrip parse(build(state)) === state', () => {
    const state = {
      search: 'bio', page: 2, sortBy: 'funding_amount' as const, sortDir: 'asc' as const,
      filters: { industry: 'Biotech' },
    };
    const round = parseListParams(buildListParams(state, FILTER_KEYS), FILTER_KEYS);
    expect(round).toEqual(state);
  });

  it("ignore les filtres vides et les cles inconnues", () => {
    const params = buildListParams(
      {
        search: '', page: 1, sortBy: 'created_at', sortDir: 'desc',
        filters: { industry: '', hacker_key: 'x' },
      },
      FILTER_KEYS,
    );
    expect(params.toString()).toBe('');
  });
});

describe('companiesListUrl', () => {
  beforeEach(() => sessionStorage.clear());

  it('sans etat memorise -> /companies nu', () => {
    expect(companiesListUrl()).toBe('/companies');
  });

  it('restaure le dernier querystring memorise', () => {
    saveCompaniesListQuery('industry=Biotech&page=2');
    expect(companiesListUrl()).toBe('/companies?industry=Biotech&page=2');
  });

  it('querystring vide -> efface la memoire', () => {
    saveCompaniesListQuery('industry=Biotech');
    saveCompaniesListQuery('');
    expect(companiesListUrl()).toBe('/companies');
  });
});
