// =============================================================================
// FGA CRM - AiCard : carte "Next best action" reutilisable
// =============================================================================
//
// Composant partage par CompanyDetail / ContactDetail / DealDetail (DC8).
// Affiche la suggestion contextuelle renvoyee par les endpoints
// /api/v1/{companies|contacts|deals}/{id}/next-action.
//
// Etats geres (DC5) :
// - loading       -> skeleton
// - data === null -> rendu null (cas deal stage='lost' : 204 backend)
// - data presente -> title + body + 1 ou 2 boutons d'action
// =============================================================================

import { Sparkles, Send } from 'lucide-react';
import { Button } from '../ui';
import type { NextActionAction, NextActionResponse } from '../../types';

interface AiCardProps {
  data: NextActionResponse | null | undefined;
  loading?: boolean;
  // Callback declenche quand l'utilisateur clique sur primary_action ou secondary_action.
  // Le parent decide quoi faire selon `action.type` (compose_email -> ouvrir composer, etc.)
  onAction?: (action: NextActionAction) => void;
}

export default function AiCard({ data, loading, onAction }: AiCardProps) {
  // Etat loading : skeleton sobre (DC5)
  if (loading) {
    return (
      <div className="relative overflow-hidden rounded-xl border border-violet-200/60 bg-gradient-to-br from-violet-50/40 to-indigo-50/30 p-4 space-y-2.5">
        <div className="flex items-center gap-2 text-[11px] font-semibold text-violet-700 uppercase tracking-wider">
          <Sparkles className="w-3 h-3" />
          Next best action
        </div>
        <div className="h-4 w-3/4 bg-violet-100/60 rounded animate-pulse" />
        <div className="h-3 w-full bg-violet-100/40 rounded animate-pulse" />
        <div className="h-3 w-5/6 bg-violet-100/40 rounded animate-pulse" />
      </div>
    );
  }

  // Pas de suggestion (cas 204 sur deal lost) : on n'affiche rien
  if (!data) return null;

  return (
    <div className="relative overflow-hidden rounded-xl border border-violet-200/60 bg-gradient-to-br from-violet-50/40 to-indigo-50/30 p-4 space-y-2.5">
      <div className="absolute -top-12 -right-6 w-36 h-36 bg-violet-300/20 rounded-full blur-2xl pointer-events-none" />
      <div className="flex items-center gap-2 text-[11px] font-semibold text-violet-700 uppercase tracking-wider">
        <Sparkles className="w-3 h-3" />
        Next best action
      </div>
      <h3 className="text-sm font-semibold text-slate-900 tracking-tight leading-snug">
        {data.title}
      </h3>
      <p className="text-xs text-slate-600 leading-relaxed">{data.body}</p>
      {(data.primary_action || data.secondary_action) && (
        <div className="flex gap-1.5 pt-1 flex-wrap">
          {data.primary_action && (
            <Button
              variant="primary"
              size="sm"
              icon={Send}
              onClick={() => onAction?.(data.primary_action!)}
            >
              {data.primary_action.label}
            </Button>
          )}
          {data.secondary_action && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onAction?.(data.secondary_action!)}
            >
              {data.secondary_action.label}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
