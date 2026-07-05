// =============================================================================
// FGA CRM - Types : AI Next-Action & Drafts
// =============================================================================
// Reponse des endpoints GET /companies|contacts|deals/{id}/next-action.
// Cas particulier : sur un deal stage='lost', le backend retourne 204 No Content
// — le client (api/client.ts) doit alors retourner null.

export type NextActionType = 'compose_email' | 'create_task' | 'snooze' | 'view' | 'find_email';

export interface NextActionAction {
  label: string;
  type: NextActionType;
}

export interface NextActionResponse {
  title: string;
  body: string;
  primary_action: NextActionAction | null;
  secondary_action: NextActionAction | null;
}

// Reponse aggregee du dashboard : 1 a 3 suggestions hebdomadaires (DC1 — borne).
// Le backend renvoie un tableau vide si rien a suggerer (cas non bloquant).
export type DashboardNextActions = NextActionResponse[];

// ---------- Drafts à valider ----------

export type { DraftReview, DraftStatus, DraftBrand } from './draft';
