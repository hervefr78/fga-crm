// =============================================================================
// FGA CRM - Types : Form Data (payloads de formulaires create/update)
// =============================================================================

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
  address_line?: string;
  postal_code?: string;
  city?: string;
  country?: string;
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
  pricing_type: string;
  recurring_amount?: number;
  commitment_months?: number;
  // Raison de perte (saisie libre, max 255 cote backend)
  loss_reason?: string;
}

export interface TaskFormData {
  title: string;
  description?: string;
  type: string;
  priority: string;
  due_date?: string;
  contact_id?: string;
  deal_id?: string;
}

export interface ActivityFormData {
  type: string;
  subject?: string;
  content?: string;
  contact_id?: string;
  company_id?: string;
  deal_id?: string;
}
