// =============================================================================
// FGA CRM - Companies : etat de vue de la liste (URL <-> etat, persistance)
// =============================================================================
// La liste Entreprises porte son etat de vue (recherche, page, tri, filtres)
// dans l'URL (?q=&page=&sort_by=&industry=...) : le retour depuis une fiche
// (back navigateur) restaure la liste EXACTEMENT telle quelle — filtres compris.
// Le dernier querystring est aussi memorise (sessionStorage) pour les liens
// "Entreprises" du split-view detail, qui pointent vers /companies "nu".
//
// Fonctions pures (parse/build) : validation DC1 des valeurs venant de l'URL.
// =============================================================================

// Colonnes triables cote backend (source unique pour la page — DC8).
export const COMPANY_SORT_KEYS = [
  'name', 'industry', 'size_range', 'created_at', 'funding_amount',
] as const;
export type CompanySortKey = (typeof COMPANY_SORT_KEYS)[number];

const SORT_KEY_SET: ReadonlySet<string> = new Set(COMPANY_SORT_KEYS);

const DEFAULT_SORT_BY: CompanySortKey = 'created_at';
const DEFAULT_SORT_DIR = 'desc' as const;
const MAX_TEXT_LEN = 200; // borne DC1 sur les valeurs texte issues de l'URL

export interface CompaniesListState {
  search: string;
  page: number;
  sortBy: CompanySortKey;
  sortDir: 'asc' | 'desc';
  filters: Record<string, string>;
}

const clip = (v: string) => v.slice(0, MAX_TEXT_LEN);

/** Lit l'etat de vue depuis l'URL. Valeurs invalides -> defauts (DC1). */
export function parseListParams(
  params: URLSearchParams,
  filterKeys: readonly string[],
): CompaniesListState {
  const rawPage = Number(params.get('page'));
  const rawSortBy = params.get('sort_by') ?? '';
  const filters: Record<string, string> = {};
  for (const key of filterKeys) {
    const v = params.get(key);
    if (v) filters[key] = clip(v);
  }
  return {
    search: clip(params.get('q') ?? ''),
    page: Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1,
    sortBy: SORT_KEY_SET.has(rawSortBy) ? (rawSortBy as CompanySortKey) : DEFAULT_SORT_BY,
    sortDir: params.get('sort_dir') === 'asc' ? 'asc' : DEFAULT_SORT_DIR,
    filters,
  };
}

/** Serialise l'etat de vue en query params — omet les defauts (URL propre). */
export function buildListParams(
  state: CompaniesListState,
  filterKeys: readonly string[],
): URLSearchParams {
  const params = new URLSearchParams();
  if (state.search) params.set('q', state.search);
  if (state.page > 1) params.set('page', String(state.page));
  if (state.sortBy !== DEFAULT_SORT_BY || state.sortDir !== DEFAULT_SORT_DIR) {
    params.set('sort_by', state.sortBy);
    params.set('sort_dir', state.sortDir);
  }
  for (const key of filterKeys) {
    const v = state.filters[key];
    if (v) params.set(key, v);
  }
  return params;
}

// ---------------------------------------------------------------------------
// Persistance du dernier querystring (pour les liens de retour du detail)
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'fga.companies.list-query';

export function saveCompaniesListQuery(querystring: string): void {
  try {
    if (querystring) sessionStorage.setItem(STORAGE_KEY, querystring);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // sessionStorage indispo (mode prive strict) : le back navigateur couvre
    // quand meme le retour via l'URL.
  }
}

/** URL de la liste avec le dernier etat de vue connu (ou /companies nu). */
export function companiesListUrl(): string {
  try {
    const qs = sessionStorage.getItem(STORAGE_KEY);
    return qs ? `/companies?${qs}` : '/companies';
  } catch {
    return '/companies';
  }
}
