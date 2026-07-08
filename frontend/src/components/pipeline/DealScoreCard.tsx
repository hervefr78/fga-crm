// =============================================================================
// FGA CRM - Deal : carte "Score IA" (workflow scoring)
// =============================================================================
// Affiche le score IA du deal (0-100, tier A/B/C, decomposition fit/intent/
// message, rationale, signaux manquants) et permet de (re)scorer. Le score est
// persiste cote backend (POST /deals/{id}/score, cache 7 jours, force possible).
// Aucun chiffre invente : les champs absents affichent — (charte UI).
// =============================================================================

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Gauge, Sparkles } from 'lucide-react';
import clsx from 'clsx';

import { scoreDeal } from '../../api/client';
import type { Deal } from '../../types';
import { Button } from '../ui';

// Couleurs par tier (A vert, B ambre, C gris — pas de gradient, charte)
const TIER_STYLES: Record<string, string> = {
  A: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  B: 'bg-amber-50 text-amber-700 border-amber-200',
  C: 'bg-slate-100 text-slate-600 border-slate-200',
};

const PRODUCT_LABELS: Record<string, string> = {
  'audit-999': 'Audit clarté (999 €)',
  'founder-499': 'Accompagnement fondateur (499 €)',
  advisory: 'Advisory',
};

function formatScoredAt(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

export default function DealScoreCard({ deal }: { deal: Deal }) {
  const queryClient = useQueryClient();
  const [showMissing, setShowMissing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const scoreMutation = useMutation({
    mutationFn: () => scoreDeal(deal.id, deal.ai_score != null),
    onSuccess: () => {
      setErrorMsg(null);
      void queryClient.invalidateQueries({ queryKey: ['deal', deal.id] });
      void queryClient.invalidateQueries({ queryKey: ['deals'] });
    },
    onError: () => setErrorMsg('Scoring indisponible. Réessayez plus tard.'),
  });

  const scored = deal.ai_score != null;
  const meta = deal.ai_score_meta ?? {};
  const missing = deal.ai_score_missing ?? [];
  const recommended = meta.recommended_product
    ? PRODUCT_LABELS[meta.recommended_product] ?? meta.recommended_product
    : null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <Gauge className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-sm font-semibold text-slate-800">Score IA</span>
        {scored && (
          <span className="text-[11px] text-slate-400">
            {formatScoredAt(deal.ai_scored_at)}
          </span>
        )}
        <div className="flex-1" />
        <Button
          variant="secondary"
          size="sm"
          icon={Sparkles}
          loading={scoreMutation.isPending}
          disabled={scoreMutation.isPending}
          onClick={() => scoreMutation.mutate()}
        >
          {scoreMutation.isPending ? 'Scoring…' : scored ? 'Re-scorer' : 'Scorer'}
        </Button>
      </div>

      <div className="p-4">
        {!scored ? (
          <p className="text-sm text-slate-400">
            Pas encore scoré. Le scoring croise le fit ICP, l&apos;intent (activités)
            et l&apos;opportunité message (audit Startup Radar).
          </p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl font-semibold text-slate-800 tabular-nums">
                {deal.ai_score}
                <span className="text-sm text-slate-400 font-normal">/100</span>
              </span>
              <span
                className={clsx(
                  'inline-flex items-center px-2 py-0.5 rounded-md border text-sm font-medium',
                  TIER_STYLES[deal.ai_tier ?? 'C'],
                )}
              >
                Tier {deal.ai_tier}
              </span>
              {recommended && (
                <span className="text-xs text-slate-500">→ {recommended}</span>
              )}
            </div>

            {/* Decomposition (donnees reelles du scoring, jamais inventees) */}
            <div className="flex flex-wrap gap-1.5 text-[11px] text-slate-500">
              <span className="px-1.5 py-0.5 rounded bg-slate-50 tabular-nums">
                Fit {meta.fit_points ?? '—'}/50
              </span>
              <span className="px-1.5 py-0.5 rounded bg-slate-50 tabular-nums">
                Intent {meta.intent_points ?? '—'}/30
              </span>
              <span className="px-1.5 py-0.5 rounded bg-slate-50 tabular-nums">
                Message {meta.message_points ?? '—'}/20
              </span>
            </div>

            {deal.ai_score_rationale && (
              <p className="text-sm text-slate-700 leading-relaxed text-pretty">
                {deal.ai_score_rationale}
              </p>
            )}

            {missing.length > 0 && (
              <div>
                <button
                  type="button"
                  onClick={() => setShowMissing((v) => !v)}
                  className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600"
                  aria-expanded={showMissing}
                >
                  <ChevronDown
                    className={clsx('w-3 h-3 transition-transform', !showMissing && '-rotate-90')}
                  />
                  {missing.length} signal{missing.length > 1 ? 'aux' : ''} manquant{missing.length > 1 ? 's' : ''}
                </button>
                {showMissing && (
                  <ul className="mt-1.5 space-y-0.5">
                    {missing.map((m, i) => (
                      <li key={i} className="text-xs text-slate-500 flex gap-1.5">
                        <span className="text-slate-300">–</span>
                        {m}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}

        {errorMsg && <p className="mt-2 text-xs text-red-600">{errorMsg}</p>}
      </div>
    </div>
  );
}
