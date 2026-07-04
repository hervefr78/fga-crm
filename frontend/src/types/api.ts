// =============================================================================
// FGA CRM - Types : Reponses API generiques (pagination, health, recherche, import)
// =============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface HealthStatus {
  status: string;
  app: string;
  version: string;
  environment: string;
}

// ---------- Recherche globale ----------

export interface SearchResultItem {
  id: string;
  label: string;
  sub: string | null;
}

export interface GlobalSearchResponse {
  contacts: SearchResultItem[];
  companies: SearchResultItem[];
  deals: SearchResultItem[];
}

// ---------- Import CSV ----------

export interface ImportRowError {
  row: number;
  field: string;
  message: string;
}

export interface ImportResult {
  imported: number;
  errors: ImportRowError[];
}
