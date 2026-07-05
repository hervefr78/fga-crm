// =============================================================================
// FGA CRM - Audit : vue messaging (simple)
// (extraite de AuditResultPanel.tsx)
// =============================================================================

import { Lightbulb, TrendingUp } from 'lucide-react';
import clsx from 'clsx';

import { scoreBgColor, scoreColor, type RadarAxis } from './auditUtils';
import { CollapsibleSection } from './AuditAtoms';
import { RadarChart } from './AuditRadarChart';

export function MessagingAuditView({ metadata }: { metadata: Record<string, unknown> }) {
  const messagingScore = (metadata.messaging_score as number) ?? 0;
  const positioning = (metadata.positioning as string) ?? '';
  const valueProp = (metadata.value_proposition as string) ?? '';
  const differentiators = (metadata.differentiators as string[]) ?? [];
  const targetAudience = (metadata.target_audience as string) ?? '';
  const strengths = (metadata.strengths as string[]) ?? [];
  const weaknesses = (metadata.weaknesses as string[]) ?? [];
  const recommendations = (metadata.recommendations as string[]) ?? [];
  const radarAxes = (metadata.radar_axes as RadarAxis[]) ?? [];

  // Score sur 10
  const scoreDisplay = messagingScore > 0
    ? messagingScore <= 10 ? messagingScore : Math.round(messagingScore / 10)
    : 0;

  return (
    <div className="space-y-4">
      {/* Score + Radar */}
      <div className="flex flex-col sm:flex-row items-center gap-6">
        {/* Score messaging */}
        {messagingScore > 0 && (
          <div className={clsx('rounded-lg p-4 flex items-center gap-4 flex-shrink-0', scoreBgColor(messagingScore))}>
            <div className={clsx('text-4xl font-bold', scoreColor(messagingScore))}>{scoreDisplay}<span className="text-lg text-slate-400">/10</span></div>
            <div>
              <p className="text-sm font-medium text-slate-700">Score messaging</p>
              {targetAudience && <p className="text-sm text-slate-500 mt-0.5">Cible : {targetAudience}</p>}
            </div>
          </div>
        )}

        {/* Radar chart */}
        {radarAxes.length >= 3 && <RadarChart axes={radarAxes} />}
      </div>

      {/* Positioning + Value prop */}
      {(positioning || valueProp) && (
        <div className="space-y-3">
          {positioning && (
            <div>
              <p className="text-xs font-medium text-slate-400 mb-1">Positionnement</p>
              <p className="text-sm text-slate-700">{positioning}</p>
            </div>
          )}
          {valueProp && (
            <div>
              <p className="text-xs font-medium text-slate-400 mb-1">Proposition de valeur</p>
              <p className="text-sm text-slate-700">{valueProp}</p>
            </div>
          )}
        </div>
      )}

      {/* Differenciateurs */}
      {differentiators.length > 0 && (
        <CollapsibleSection title="Differenciateurs" icon={TrendingUp}>
          <ul className="space-y-1">
            {differentiators.map((d, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="text-blue-400 mt-0.5">•</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Forces + Faiblesses cote a cote */}
      {(strengths.length > 0 || weaknesses.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {strengths.length > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              <p className="text-xs font-medium text-emerald-600 mb-2">Forces</p>
              <ul className="space-y-1">
                {strengths.map((s, i) => (
                  <li key={i} className="text-sm text-emerald-800 flex items-start gap-1.5">
                    <span className="mt-0.5">+</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {weaknesses.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-xs font-medium text-red-600 mb-2">Faiblesses</p>
              <ul className="space-y-1">
                {weaknesses.map((w, i) => (
                  <li key={i} className="text-sm text-red-800 flex items-start gap-1.5">
                    <span className="mt-0.5">-</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Recommandations */}
      {recommendations.length > 0 && (
        <CollapsibleSection title="Recommandations" icon={Lightbulb}>
          <ol className="space-y-2 list-decimal list-inside">
            {recommendations.map((r, i) => (
              <li key={i} className="text-sm text-slate-600">{r}</li>
            ))}
          </ol>
        </CollapsibleSection>
      )}
    </div>
  );
}
