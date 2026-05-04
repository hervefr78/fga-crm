// =============================================================================
// FGA CRM - AiCard : carte "Next best action" reutilisable
// =============================================================================
//
// Composant partage par CompanyDetail / ContactDetail / DealDetail / Dashboard (DC8).
// Affiche la suggestion contextuelle renvoyee par les endpoints
// /api/v1/{companies|contacts|deals}/{id}/next-action
// ou la liste des suggestions hebdomadaires /api/v1/dashboard/next-actions.
//
// Etats geres (DC5) :
// - loading                                    -> skeleton
// - data === null / [] / undefined             -> rendu null (pas de chrome vide)
// - data: NextActionResponse                   -> 1 carte avec title + body + actions
// - data: NextActionResponse[] (>= 1 item)     -> stack vertical, 1 entree par suggestion
// =============================================================================

import { Sparkles, Send } from 'lucide-react';
import { Button } from '../ui';
import type { NextActionAction, NextActionResponse } from '../../types';

interface AiCardProps {
  data: NextActionResponse | NextActionResponse[] | null | undefined;
  loading?: boolean;
  // Callback declenche quand l'utilisateur clique sur primary_action ou secondary_action.
  // Le parent decide quoi faire selon `action.type` (compose_email -> ouvrir composer, etc.)
  // L'index est fourni pour les contextes multi-suggestion (dashboard).
  onAction?: (action: NextActionAction, index: number) => void;
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

  // Normaliser en tableau pour traiter uniformement (DC8 — un seul rendu)
  const items: NextActionResponse[] = Array.isArray(data)
    ? data
    : data
      ? [data]
      : [];

  // Pas de suggestion : on n'affiche rien (DC5 — pas de chrome sans contenu, UI_GUIDELINES §1.4)
  if (items.length === 0) return null;

  // Cas singulier (page detail) : layout compact d'origine
  if (items.length === 1) {
    return <SingleSuggestion item={items[0]} index={0} onAction={onAction} />;
  }

  // Cas multi (dashboard) : stack vertical avec 1 entree par suggestion.
  // On garde le chrome violet en wrapper externe pour preserver l'identite "IA".
  return (
    <div className="relative overflow-hidden rounded-xl border border-violet-200/60 bg-gradient-to-br from-violet-50/40 to-indigo-50/30 p-4">
      <div className="absolute -top-12 -right-6 w-36 h-36 bg-violet-300/20 rounded-full blur-2xl pointer-events-none" />
      <div className="flex items-center gap-2 text-[11px] font-semibold text-violet-700 uppercase tracking-wider mb-3">
        <Sparkles className="w-3 h-3" />
        Next best actions de la semaine
        <span className="ml-1 text-violet-400 tabular-nums">· {items.length}</span>
      </div>
      <ul className="space-y-3">
        {items.map((item, idx) => (
          <li
            key={idx}
            className="bg-white/60 border border-violet-100 rounded-lg p-3 space-y-2"
          >
            <h3 className="text-sm font-semibold text-slate-900 tracking-tight leading-snug">
              {item.title}
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">{item.body}</p>
            {(item.primary_action || item.secondary_action) && (
              <div className="flex gap-1.5 pt-1 flex-wrap">
                {item.primary_action && (
                  <Button
                    variant="primary"
                    size="sm"
                    icon={Send}
                    onClick={() => onAction?.(item.primary_action!, idx)}
                  >
                    {item.primary_action.label}
                  </Button>
                )}
                {item.secondary_action && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onAction?.(item.secondary_action!, idx)}
                  >
                    {item.secondary_action.label}
                  </Button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// Sous-composant : rendu d'une seule suggestion (compatible legacy)
function SingleSuggestion({
  item,
  index,
  onAction,
}: {
  item: NextActionResponse;
  index: number;
  onAction?: (action: NextActionAction, index: number) => void;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-violet-200/60 bg-gradient-to-br from-violet-50/40 to-indigo-50/30 p-4 space-y-2.5">
      <div className="absolute -top-12 -right-6 w-36 h-36 bg-violet-300/20 rounded-full blur-2xl pointer-events-none" />
      <div className="flex items-center gap-2 text-[11px] font-semibold text-violet-700 uppercase tracking-wider">
        <Sparkles className="w-3 h-3" />
        Next best action
      </div>
      <h3 className="text-sm font-semibold text-slate-900 tracking-tight leading-snug">
        {item.title}
      </h3>
      <p className="text-xs text-slate-600 leading-relaxed">{item.body}</p>
      {(item.primary_action || item.secondary_action) && (
        <div className="flex gap-1.5 pt-1 flex-wrap">
          {item.primary_action && (
            <Button
              variant="primary"
              size="sm"
              icon={Send}
              onClick={() => onAction?.(item.primary_action!, index)}
            >
              {item.primary_action.label}
            </Button>
          )}
          {item.secondary_action && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onAction?.(item.secondary_action!, index)}
            >
              {item.secondary_action.label}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
