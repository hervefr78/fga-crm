// =============================================================================
// FGA CRM - Types : Entites
// =============================================================================

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  organization_id?: string | null;
  is_superadmin?: boolean;
  avatar_url: string | null;
  created_at?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
}

// Reponse minimale du endpoint GET /users/lookup (id + full_name uniquement).
// Accessible aux managers/admins ; pour un sales le backend retourne uniquement
// son propre user, donc le filtre owner cote front sera masque (length <= 1).
export interface UserLookup {
  id: string;
  full_name: string;
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
  // Champ derive backend (joined depuis Company.name) — null si pas d'entreprise rattachee
  company_name: string | null;
  owner_id: string | null;
  owner_name: string | null;
  created_at: string;
  updated_at: string | null;
  updated_by_name: string | null;
  // Enrichment (synced from SR multi-source pipeline)
  enrichment_source?: string | null;
  email_pattern_used?: string | null;
  linkedin_url_status?: 'candidate' | 'verified' | 'invalid' | string | null;
  // Qualification IA (workflow qualification — null si non qualifie)
  ai_qualification?: {
    spiced?: Record<string, { value: string; source: string }>;
    routing_rationale?: string;
    suggested_product?: string | null;
    next_action?: string;
    model?: string;
    prompt_version?: string;
  } | null;
  ai_routing?: string | null;
  ai_qualified_at?: string | null;
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
  address_line: string | null;
  postal_code: string | null;
  city: string | null;
  country: string | null;
  startup_radar_id: string | null;
  lead_source: string | null;
  owner_id: string | null;
  owner_name: string | null;
  created_at: string;
  updated_at: string | null;
  updated_by_name: string | null;
  has_audit_messaging: boolean;
  has_audit_detailed: boolean;
  has_audit_geo: boolean;
  audit_score: number | null;
  // Funding (synced from SR multi-source pipeline)
  siren?: string | null;
  funding_date?: string | null;  // ISO date YYYY-MM-DD
  funding_amount?: number | null;  // euros
  funding_series?: string | null;
  funding_sources?: string[] | null;
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
  // Date de cloture effective (renseignee quand le deal passe a won/lost cote backend)
  actual_close_date: string | null;
  // Position dans la colonne du stage (utilisee pour l'ordonnancement custom)
  position: number;
  company_id: string | null;
  contact_id: string | null;
  owner_id: string | null;
  description: string | null;
  // Tarification (one_shot par defaut, ou recurrent : monthly/quarterly/biannual/annual)
  pricing_type: string;
  recurring_amount: number | null;
  commitment_months: number | null;
  created_at: string;
  // Champs derives backend (selectinload owner/company/contact + loss_reason colonne)
  loss_reason: string | null;
  owner_name: string | null;
  company_name: string | null;
  // Champ derive backend (joined depuis Contact.full_name) — null si pas de contact
  contact_name: string | null;
  // Produit vendu (audit-999 | founder-499 | advisory) + scoring IA (null si non score)
  product: string | null;
  ai_score: number | null;
  ai_tier: string | null;
  ai_score_rationale: string | null;
  ai_score_missing: string[];
  ai_scored_at: string | null;
  ai_score_meta: {
    model?: string | null;
    prompt_version?: string | null;
    recommended_product?: string | null;
    fit_points?: number | null;
    intent_points?: number | null;
    message_points?: number | null;
  };
}

// Stats agregees retournees par GET /api/v1/deals/stats
export interface DealsStats {
  count: number;
  total_amount: number;
  one_shot_amount: number;
  mrr: number;
  arr: number;
  recurring_count: number;
}

// Categorie d'affichage cote backend (filtre /deals?category=...)
export type DealCategory = 'pipeline' | 'signed' | 'lost';

export interface Task {
  id: string;
  title: string;
  description: string | null;
  type: string;
  priority: string;
  is_completed: boolean;
  due_date: string | null;
  completed_at: string | null;
  assigned_to: string | null;
  contact_id: string | null;
  deal_id: string | null;
  company_id?: string | null;
  created_at: string;
}

export interface Activity {
  id: string;
  type: string;
  subject: string | null;
  content: string | null;
  metadata_: Record<string, unknown> | null;
  contact_id: string | null;
  company_id: string | null;
  deal_id: string | null;
  user_id: string;
  created_at: string;
}
