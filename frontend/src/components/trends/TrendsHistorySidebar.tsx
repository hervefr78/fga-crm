// =============================================================================
// FGA CRM - Trends : sidebar historique (analyses recentes)
// =============================================================================
// Liste les analyses recentes de l'organisation (dedupliquees cote backend). Un
// clic rouvre le rapport correspondant SANS le relancer (le parent passe le
// job_id a l'etat actif, qui recharge le rapport via les queries existantes).
// =============================================================================

import clsx from 'clsx';
import { History, Sparkles } from 'lucide-react';

import type { TrendReportListItem } from '../../types/trends';
import { OBJECTIVES, TIMEFRAMES, formatScore } from './trendUtils';

const OBJECTIVE_LABEL: Record<string, string> = Object.fromEntries(
  OBJECTIVES.map((o) => [o.value, o.label]),
);
const TIMEFRAME_LABEL: Record<string, string> = Object.fromEntries(
  TIMEFRAMES.map((t) => [t.value, t.label]),
);

function formatDay(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

export function TrendsHistorySidebar({
  items, activeJobId, onSelect,
}: {
  items: TrendReportListItem[];
  activeJobId: string | null;
  onSelect: (jobId: string) => void;
}) {
  return (
    <aside className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden self-start">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 text-sm font-semibold text-slate-800">
        <History className="w-3.5 h-3.5 text-slate-400" />
        Analyses recentes
      </div>

      {items.length === 0 ? (
        <p className="px-4 py-8 text-center text-xs text-slate-400">
          Aucune analyse enregistree. Lancez une analyse pour la retrouver ici.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100 max-h-[70vh] overflow-y-auto">
          {items.map((it) => {
            const active = it.job_id === activeJobId;
            const objective = it.objective ? OBJECTIVE_LABEL[it.objective] : null;
            return (
              <li key={it.job_id}>
                <button
                  type="button"
                  onClick={() => onSelect(it.job_id)}
                  aria-current={active}
                  className={clsx(
                    'w-full text-left px-4 py-3 transition-colors',
                    active ? 'bg-primary-50' : 'hover:bg-slate-50',
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-slate-800 truncate">
                      {it.category_label}
                    </span>
                    <span className="text-xs text-slate-500 tabular-nums shrink-0">
                      {formatScore(it.opportunity_score)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                    {objective && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-primary-700 bg-primary-50 border border-primary-100 rounded px-1.5 py-0.5">
                        <Sparkles className="w-2.5 h-2.5" />
                        {objective}
                      </span>
                    )}
                    <span className="text-[11px] text-slate-400">
                      {TIMEFRAME_LABEL[it.timeframe] ?? it.timeframe}
                    </span>
                    <span className="text-[11px] text-slate-300">·</span>
                    <span className="text-[11px] text-slate-400">{formatDay(it.created_at)}</span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
