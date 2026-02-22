// =============================================================================
// FGA CRM - TypeScript Types
// =============================================================================

// ---------- Entites ----------

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
  country: string | null;
  city: string | null;
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

// ---------- Reponses API ----------

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

// ---------- Form Data ----------

export interface ContactFormData {
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  title?: string;
  job_level?: string;
  department?: string;
  linkedin_url?: string;
  company_id?: string;
  source?: string;
  status: string;
  is_decision_maker?: boolean;
}

export interface CompanyFormData {
  name: string;
  domain?: string;
  website?: string;
  industry?: string;
  description?: string;
  size_range?: string;
  linkedin_url?: string;
  phone?: string;
  country?: string;
  city?: string;
}

export interface DealFormData {
  title: string;
  stage: string;
  amount?: number;
  currency: string;
  probability: number;
  priority: string;
  expected_close_date?: string;
  company_id?: string;
  contact_id?: string;
  description?: string;
}

// ---------- Constantes (dropdowns) ----------

export const CONTACT_STATUSES = [
  { value: 'new', label: 'Nouveau' },
  { value: 'contacted', label: 'Contacté' },
  { value: 'qualified', label: 'Qualifié' },
  { value: 'unqualified', label: 'Non qualifié' },
  { value: 'nurturing', label: 'Nurturing' },
] as const;

export const JOB_LEVELS = [
  { value: 'C-Level', label: 'C-Level' },
  { value: 'VP', label: 'VP' },
  { value: 'Director', label: 'Directeur' },
  { value: 'Manager', label: 'Manager' },
  { value: 'IC', label: 'IC' },
  { value: 'Other', label: 'Autre' },
] as const;

export const DEAL_STAGES = [
  { value: 'new', label: 'Nouveau' },
  { value: 'contacted', label: 'Contacté' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'proposal', label: 'Proposition' },
  { value: 'negotiation', label: 'Négociation' },
  { value: 'won', label: 'Gagné' },
  { value: 'lost', label: 'Perdu' },
] as const;

export const DEAL_PRIORITIES = [
  { value: 'low', label: 'Basse' },
  { value: 'medium', label: 'Moyenne' },
  { value: 'high', label: 'Haute' },
  { value: 'urgent', label: 'Urgente' },
] as const;

export const COMPANY_SIZE_RANGES = [
  { value: '1-10', label: '1-10' },
  { value: '11-50', label: '11-50' },
  { value: '51-200', label: '51-200' },
  { value: '201-500', label: '201-500' },
  { value: '500+', label: '500+' },
] as const;
