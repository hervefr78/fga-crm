// =============================================================================
// FGA CRM - TypeScript Types
// =============================================================================

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface Contact {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  email_status: string | null;
  phone: string | null;
  title: string | null;
  job_level: string | null;
  department: string | null;
  is_decision_maker: boolean;
  linkedin_url: string | null;
  status: string;
  lead_score: number;
  source: string | null;
  company_id: string | null;
  owner_id: string | null;
  created_at: string;
}

export interface Company {
  id: string;
  name: string;
  domain: string | null;
  website: string | null;
  industry: string | null;
  description: string | null;
  size_range: string | null;
  linkedin_url: string | null;
  phone: string | null;
  owner_id: string | null;
  created_at: string;
}

export interface Deal {
  id: string;
  title: string;
  stage: string;
  amount: number | null;
  currency: string;
  probability: number;
  priority: string;
  expected_close_date: string | null;
  company_id: string | null;
  contact_id: string | null;
  owner_id: string | null;
  description: string | null;
  created_at: string;
}

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
