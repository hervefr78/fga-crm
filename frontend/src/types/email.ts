// =============================================================================
// FGA CRM - Types : Email (templates, envoi, emails envoyes)
// =============================================================================

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
