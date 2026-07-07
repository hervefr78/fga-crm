// =============================================================================
// FGA CRM - Constantes runtime : dropdowns, roles & permissions
// =============================================================================
// ATTENTION : ce fichier expose des VALEURS runtime (pas seulement des types).
// Les tableaux `as const` et les helpers sont consommes tels quels par l'UI.

import type { User } from './entities';

// ---------- Constantes (dropdowns) ----------

export const CONTACT_STATUSES = [
  { value: 'new', label: 'Nouveau' },
  { value: 'contacted', label: 'Contacté' },
  { value: 'qualified', label: 'Qualifié' },
  { value: 'unqualified', label: 'Non qualifié' },
  { value: 'nurturing', label: 'Nurturing' },
] as const;

export const JOB_LEVELS = [
  { value: 'CxO', label: 'CxO' },
  { value: 'Director', label: 'Director' },
  { value: 'Manager', label: 'Manager' },
  { value: 'User', label: 'User' },
  { value: 'Partner', label: 'Partner' },
  { value: 'Investor', label: 'Investor' },
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

export const DEAL_PRICING_TYPES = [
  { value: 'one_shot', label: 'Coût unique' },
  { value: 'monthly', label: 'Abonnement mensuel' },
  { value: 'quarterly', label: 'Abonnement trimestriel' },
  { value: 'biannual', label: 'Abonnement semestriel' },
  { value: 'annual', label: 'Abonnement annuel' },
] as const;

// Helper : nombre de mois par periode (utile pour calculer MRR cote front)
export const PRICING_PERIOD_MONTHS: Record<string, number> = {
  monthly: 1,
  quarterly: 3,
  biannual: 6,
  annual: 12,
};

export const COMPANY_SIZE_RANGES = [
  { value: '1-10', label: '1-10' },
  { value: '11-50', label: '11-50' },
  { value: '51-200', label: '51-200' },
  { value: '201-500', label: '201-500' },
  { value: '500+', label: '500+' },
] as const;

// Provenances CRM (lead_source) — valeurs ALIGNEES sur ce que les integrations
// ecrivent en base (DC10 : 'plein-phare' avec tiret). Source unique (DC8) pour
// le filtre Entreprises et le mode source de l'enrichissement.
export const LEAD_SOURCES = [
  { value: 'startup_radar', label: 'Startup Radar' },
  { value: 'nomo-ia', label: 'Nomo-IA' },
  { value: 'plein-phare', label: 'Plein Phare Digital' },
] as const;

export const TASK_TYPES = [
  { value: 'todo', label: 'À faire' },
  { value: 'call', label: 'Appel' },
  { value: 'email', label: 'Email' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'qualification', label: 'Qualification levée' },
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
  { value: 'startup_radar', label: 'Startup Radar' },
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
  { value: 'funding_detected', label: 'Levée détectée' },
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
