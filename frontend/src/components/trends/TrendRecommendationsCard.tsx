// =============================================================================
// FGA CRM - Trends : carte "Recommandations IA" (mode Profond)
// =============================================================================
// Rend les recommandations LLM d'un rapport Trends : synthese strategique,
// mots-cles a cibler, requetes a surveiller, angles de contenu. Affichee
// uniquement si le rapport porte des recommandations (deep + LLM disponible).
// =============================================================================

import type { ElementType, ReactNode } from 'react';
import { Eye, PenLine, Sparkles, Target } from 'lucide-react';

import type { TrendRecommendations } from '../../types/trends';
import { OBJECTIVES } from './trendUtils';

const OBJECTIVE_LABEL: Record<string, string> = Object.fromEntries(
  OBJECTIVES.map((o) => [o.value, o.label]),
);

export function TrendRecommendationsCard({ reco }: { reco: TrendRecommendations }) {
  const objectiveLabel = reco.objective ? OBJECTIVE_LABEL[reco.objective] : null;

  return (
    <div className="bg-white border border-primary-100 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-primary-100 bg-primary-50/40 flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-primary-100 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-primary-600" />
        </div>
        <span className="text-sm font-semibold text-slate-800">Recommandations IA</span>
        {objectiveLabel && (
          <span className="ml-auto text-[11px] font-medium text-primary-700 bg-primary-50 border border-primary-100 rounded px-2 py-0.5">
            {objectiveLabel}
          </span>
        )}
      </div>

      <div className="p-4 space-y-5">
        {reco.strategy && (
          <p className="text-sm text-slate-700 leading-relaxed text-pretty">{reco.strategy}</p>
        )}

        {reco.target_keywords.length > 0 && (
          <Section icon={Target} title="Mots-cles a cibler">
            <ul className="space-y-2">
              {reco.target_keywords.map((k, i) => (
                <li key={`${k.keyword}-${i}`} className="flex items-start gap-2">
                  <span className="text-xs font-medium text-slate-800 bg-slate-100 rounded px-2 py-0.5 shrink-0">
                    {k.keyword}
                  </span>
                  <span className="text-xs text-slate-500 leading-relaxed">
                    {k.cluster && <span className="text-slate-400">{k.cluster} · </span>}
                    {k.rationale}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {reco.watch_queries.length > 0 && (
          <Section icon={Eye} title="A surveiller">
            <ul className="space-y-2">
              {reco.watch_queries.map((w, i) => (
                <li key={`${w.query}-${i}`} className="flex items-start gap-2">
                  <span className="text-xs font-medium text-slate-800 bg-amber-50 border border-amber-100 rounded px-2 py-0.5 shrink-0">
                    {w.query}
                  </span>
                  <span className="text-xs text-slate-500 leading-relaxed">{w.reason}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {reco.content_angles.length > 0 && (
          <Section icon={PenLine} title="Angles de contenu">
            <ul className="space-y-1.5">
              {reco.content_angles.map((a, i) => (
                <li key={i} className="text-sm text-slate-700 flex gap-2">
                  <span className="text-slate-300">–</span>
                  <span>{a}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({
  icon: Icon, title, children,
}: {
  icon: ElementType;
  title: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        <Icon className="w-3.5 h-3.5 text-slate-400" />
        {title}
      </div>
      {children}
    </div>
  );
}
