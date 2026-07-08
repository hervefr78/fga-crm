// =============================================================================
// FGA CRM - Dashboard : carte "Insights IA" (synthese hebdo du pipeline)
// =============================================================================
// Reserve aux managers/admins (le parent gate l'affichage — l'endpoint est
// egalement manager+ cote backend). Affiche la derniere synthese (< 24 h en
// cache) : sante du pipeline, deals stagnants, patterns de perte, 3 actions.
// Aucun chiffre invente : tout vient des agregats org (prompt insights-v1).
// =============================================================================

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, BrainCircuit, RefreshCw } from 'lucide-react';

import { getWeeklyInsights } from '../../api/client';

interface Insights {
  headline: string;
  pipeline_health: string;
  stale_deals_summary: string;
  loss_patterns: string | null;
  top_actions: string[];
  data_caveats: string[];
  generated_at: string;
  cached: boolean;
}

function formatGeneratedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export default function InsightsCard() {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, isFetching, refetch } = useQuery<Insights>({
    queryKey: ['weekly-insights'],
    queryFn: () => getWeeklyInsights(false),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const forceRefresh = async () => {
    // refresh=true regenere cote backend, puis met a jour le cache local.
    const fresh = await getWeeklyInsights(true);
    queryClient.setQueryData(['weekly-insights'], fresh);
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <BrainCircuit className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-sm font-semibold text-slate-800">Insights IA — pipeline</span>
        {data && (
          <span className="text-[11px] text-slate-400">{formatGeneratedAt(data.generated_at)}</span>
        )}
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => void forceRefresh().catch(() => refetch())}
          disabled={isFetching}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-700 disabled:opacity-50"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Actualiser
        </button>
      </div>

      <div className="p-4">
        {isLoading ? (
          <p className="text-sm text-slate-400">Génération de la synthèse…</p>
        ) : isError || !data ? (
          <p className="text-sm text-slate-400 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            Synthèse indisponible pour le moment.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-medium text-slate-800">{data.headline}</p>
            <p className="text-sm text-slate-600 leading-relaxed">{data.pipeline_health}</p>
            {data.stale_deals_summary && (
              <p className="text-sm text-slate-600 leading-relaxed">{data.stale_deals_summary}</p>
            )}
            {data.loss_patterns && (
              <p className="text-sm text-slate-600 leading-relaxed">{data.loss_patterns}</p>
            )}

            {data.top_actions.length > 0 && (
              <div>
                <span className="text-[11px] uppercase tracking-wide text-slate-400">
                  Actions prioritaires
                </span>
                <ul className="mt-1 space-y-1">
                  {data.top_actions.map((a, i) => (
                    <li key={i} className="text-sm text-slate-700 flex gap-2">
                      <span className="text-slate-300 tabular-nums">{i + 1}.</span>
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {data.data_caveats.length > 0 && (
              <p className="text-[11px] text-slate-400">
                {data.data_caveats.join(' · ')}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
