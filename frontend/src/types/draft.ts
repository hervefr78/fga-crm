// =============================================================================
// FGA CRM - Types Drafts à valider
// =============================================================================
// Miroir EXACT du schema backend compass-core (app/schemas/draft.py — DraftRecord),
// expose via le proxy CRM /api/v1/drafts-review. Ne pas deviner les noms de champs (DC10).

// Statuts de revue d'un draft. Le backend cree les drafts en 'to-review' par defaut ;
// l'operateur les passe en 'approved' ou 'rejected' ; 'published' est positionne
// par le MCP apres publication.
export type DraftStatus = 'to-review' | 'approved' | 'rejected' | 'published';

// Marques gerees par le pipeline de generation.
export type DraftBrand = 'fga' | 'nomo' | 'ppd';

// Draft genere par le MCP, stocke dans compass-core, expose via le proxy CRM.
// `status` reste un string libre cote API (le backend ne le borne pas a l'enum) ;
// on le type donc `string` pour rester fidele au contrat et eviter les casts hasardeux.
export interface DraftReview {
  draft_id: string;
  lead_id: string;
  type: string;
  content: string;
  status: string;
  brand: DraftBrand;
  sequence_day: number | null;
  voice_pack_used: string | null;
  voice_check_passed: boolean;
  published_url: string | null;
  created_by: string;
  created_at: string | null;
  metadata: Record<string, unknown> | null;
}
