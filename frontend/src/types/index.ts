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
  avatar_url: string | null;
  created_at?: string;
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
  startup_radar_id: string | null;
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

export const TASK_TYPES = [
  { value: 'todo', label: 'À faire' },
  { value: 'call', label: 'Appel' },
  { value: 'email', label: 'Email' },
  { value: 'meeting', label: 'Meeting' },
] as const;

export const TASK_PRIORITIES = [
  { value: 'low', label: 'Basse' },
  { value: 'medium', label: 'Moyenne' },
  { value: 'high', label: 'Haute' },
  { value: 'urgent', label: 'Urgente' },
] as const;

export const CONTACT_SOURCES = [
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'website', label: 'Site web' },
  { value: 'referral', label: 'Recommandation' },
  { value: 'event', label: 'Événement' },
  { value: 'cold_outreach', label: 'Prospection' },
  { value: 'inbound', label: 'Inbound' },
  { value: 'other', label: 'Autre' },
] as const;

export const ACTIVITY_TYPES = [
  { value: 'email', label: 'Email' },
  { value: 'call', label: 'Appel' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'note', label: 'Note' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'task', label: 'Tâche' },
  { value: 'audit', label: 'Audit' },
] as const;

// ---------- Roles & Permissions ----------

export const USER_ROLES = [
  { value: 'admin', label: 'Administrateur' },
  { value: 'manager', label: 'Manager' },
  { value: 'sales', label: 'Commercial' },
] as const;

export type UserRole = 'admin' | 'manager' | 'sales';

export function isAdmin(user: User | null): boolean {
  return user?.role === 'admin';
}

export function isManagerOrAbove(user: User | null): boolean {
  return user?.role === 'admin' || user?.role === 'manager';
}

// ---------- Email ----------

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  variables: string[];
  owner_id: string;
  created_at: string;
}

export interface EmailTemplateFormData {
  name: string;
  subject: string;
  body: string;
}

export interface EmailSendData {
  to_email: string;
  subject: string;
  body: string;
  contact_id?: string;
  company_id?: string;
  deal_id?: string;
  template_id?: string;
}

export interface EmailSendResponse {
  success: boolean;
  activity_id: string;
  message_id: string | null;
  sent_at: string;
}

export interface SentEmail {
  id: string;
  subject: string | null;
  content: string | null;
  to_email: string;
  from_email: string;
  template_name: string | null;
  contact_id: string | null;
  company_id: string | null;
  deal_id: string | null;
  user_id: string;
  created_at: string;
}

export const TEMPLATE_VARIABLES = [
  { key: 'first_name', label: 'Prenom du contact' },
  { key: 'last_name', label: 'Nom du contact' },
  { key: 'full_name', label: 'Nom complet' },
  { key: 'email', label: 'Email du contact' },
  { key: 'title', label: 'Titre du contact' },
  { key: 'company_name', label: 'Nom de l\'entreprise' },
  { key: 'sender_name', label: 'Nom de l\'expediteur' },
  { key: 'sender_email', label: 'Email de l\'expediteur' },
] as const;

// ---------- Integrations (Startup Radar) ----------

export interface SyncResult {
  companies_created: number;
  companies_updated: number;
  contacts_created: number;
  contacts_updated: number;
  investors_created: number;
  investors_updated: number;
  audits_created: number;
  errors: string[];
}

export interface SyncStatus {
  has_synced: boolean;
  last_result: SyncResult | null;
}

export interface CompanyAuditResponse {
  audits_created: number;
  audits_skipped: number;
  errors: string[];
}

// ---------- Dashboard Stats ----------

export interface DealsByStage {
  stage: string;
  count: number;
  total_amount: number;
}

export interface ActivityByType {
  type: string;
  count: number;
}

export interface DashboardStats {
  contacts_total: number;
  contacts_this_month: number;
  companies_total: number;
  deals_total: number;
  deals_pipeline_amount: number;
  deals_won_amount: number;
  deals_won_count: number;
  deals_lost_count: number;
  deals_by_stage: DealsByStage[];
  activities_by_type: ActivityByType[];
  activities_total_30d: number;
  tasks_total: number;
  tasks_completed: number;
  tasks_overdue: number;
  emails_sent_30d: number;
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
