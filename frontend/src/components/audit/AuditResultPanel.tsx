// =============================================================================
// FGA CRM - Panneau de resultats d'audit Startup Radar
// Affiche les audits detailles et messaging dans la fiche entreprise
// =============================================================================

import { AlertTriangle, Award, ChevronDown, ChevronUp, Lightbulb, Target, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';

// Seuils de score pour les couleurs
const SCORE_THRESHOLDS = { good: 70, medium: 40 } as const;

function scoreColor(score: number): string {
  if (score >= SCORE_THRESHOLDS.good) return 'text-emerald-600';
  if (score >= SCORE_THRESHOLDS.medium) return 'text-amber-600';
  return 'text-red-500';
}

function scoreBgColor(score: number): string {
  if (score >= SCORE_THRESHOLDS.good) return 'bg-emerald-50';
  if (score >= SCORE_THRESHOLDS.medium) return 'bg-amber-50';
  return 'bg-red-50';
}

function scoreBarColor(score: number): string {
  if (score >= SCORE_THRESHOLDS.good) return 'bg-emerald-500';
  if (score >= SCORE_THRESHOLDS.medium) return 'bg-amber-500';
  return 'bg-red-500';
}

// ---------------------------------------------------------------------------
// Barre de score
// ---------------------------------------------------------------------------

function ScoreBar({ label, score, max = 100 }: { label: string; score: number; max?: number }) {
  const pct = Math.min(Math.round((score / max) * 100), 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-600 w-28 flex-shrink-0 truncate">{label}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-2">
        <div
          className={clsx('h-2 rounded-full transition-all duration-500', scoreBarColor(pct))}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={clsx('text-sm font-semibold w-10 text-right', scoreColor(pct))}>{score}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section pliable
// ---------------------------------------------------------------------------

function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 rounded-lg">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-slate-400" />
          <span>{title}</span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      {open && <div className="px-4 pb-4 border-t border-slate-100 pt-3">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vue audit detaille
// ---------------------------------------------------------------------------

function DetailedAuditView({ metadata }: { metadata: Record<string, unknown> }) {
  const totalScore = (metadata.total_score as number) ?? 0;
  const interpretation = (metadata.score_interpretation as string) ?? '';
  const keyFindings = (metadata.key_findings as string[]) ?? [];
  const topPriority = (metadata.top_priority as string) ?? '';
  const scoring = (metadata.scoring as Record<string, unknown>) ?? {};
  const gapsCount = (metadata.gaps_count as number) ?? 0;
  const recsCount = (metadata.recommendations_count as number) ?? 0;

  return (
    <div className="space-y-4">
      {/* Score principal */}
      <div className={clsx('rounded-lg p-4 flex items-center gap-4', scoreBgColor(totalScore))}>
        <div className={clsx('text-4xl font-bold', scoreColor(totalScore))}>{totalScore}</div>
        <div>
          <p className="text-sm font-medium text-slate-700">Score global</p>
          {interpretation && <p className="text-sm text-slate-500 mt-0.5">{interpretation}</p>}
        </div>
      </div>

      {/* Stats rapides */}
      <div className="flex items-center gap-4 text-sm">
        {gapsCount > 0 && (
          <div className="flex items-center gap-1.5 text-amber-600">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{gapsCount} gap{gapsCount > 1 ? 's' : ''} identifie{gapsCount > 1 ? 's' : ''}</span>
          </div>
        )}
        {recsCount > 0 && (
          <div className="flex items-center gap-1.5 text-blue-600">
            <Lightbulb className="w-3.5 h-3.5" />
            <span>{recsCount} recommandation{recsCount > 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      {/* Priorite */}
      {topPriority && (
        <div className="bg-violet-50 border border-violet-200 rounded-lg p-3">
          <p className="text-xs font-medium text-violet-600 mb-1">Priorite principale</p>
          <p className="text-sm text-violet-900">{topPriority}</p>
        </div>
      )}

      {/* Key findings */}
      {keyFindings.length > 0 && (
        <CollapsibleSection title="Points cles" icon={Target}>
          <ul className="space-y-2">
            {keyFindings.map((finding, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="text-slate-400 mt-0.5">•</span>
                <span>{finding}</span>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Scoring breakdown */}
      {Object.keys(scoring).length > 0 && (
        <CollapsibleSection title="Scores par categorie" icon={Award}>
          <div className="space-y-3">
            {Object.entries(scoring).map(([key, value]) => {
              // Le scoring peut etre un objet avec score/max ou directement un nombre
              const numValue = typeof value === 'number'
                ? value
                : typeof value === 'object' && value !== null && 'score' in value
                  ? (value as { score: number }).score
                  : 0;
              const maxValue = typeof value === 'object' && value !== null && 'max' in value
                ? (value as { max: number }).max
                : 100;
              const label = key
                .replace(/_/g, ' ')
                .replace(/\b\w/g, (c) => c.toUpperCase());
              return <ScoreBar key={key} label={label} score={numValue} max={maxValue} />;
            })}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vue audit messaging
// ---------------------------------------------------------------------------

function MessagingAuditView({ metadata }: { metadata: Record<string, unknown> }) {
  const messagingScore = (metadata.messaging_score as number) ?? 0;
  const positioning = (metadata.positioning as string) ?? '';
  const valueProp = (metadata.value_proposition as string) ?? '';
  const differentiators = (metadata.differentiators as string[]) ?? [];
  const targetAudience = (metadata.target_audience as string) ?? '';
  const strengths = (metadata.strengths as string[]) ?? [];
  const weaknesses = (metadata.weaknesses as string[]) ?? [];
  const recommendations = (metadata.recommendations as string[]) ?? [];

  return (
    <div className="space-y-4">
      {/* Score messaging */}
      {messagingScore > 0 && (
        <div className={clsx('rounded-lg p-4 flex items-center gap-4', scoreBgColor(messagingScore))}>
          <div className={clsx('text-4xl font-bold', scoreColor(messagingScore))}>{messagingScore}</div>
          <div>
            <p className="text-sm font-medium text-slate-700">Score messaging</p>
            {targetAudience && <p className="text-sm text-slate-500 mt-0.5">Cible : {targetAudience}</p>}
          </div>
        </div>
      )}

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

// ---------------------------------------------------------------------------
// Composant principal
// ---------------------------------------------------------------------------

interface AuditResultPanelProps {
  metadata: Record<string, unknown>;
  subject: string;
  createdAt: string;
}

export default function AuditResultPanel({ metadata, subject, createdAt }: AuditResultPanelProps) {
  const auditType = (metadata.audit_type as string) ?? '';
  const formattedDate = new Date(createdAt).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">{subject}</h3>
        <span className="text-xs text-slate-400">{formattedDate}</span>
      </div>
      {/* Body */}
      <div className="p-5">
        {auditType === 'detailed' && <DetailedAuditView metadata={metadata} />}
        {auditType === 'messaging' && <MessagingAuditView metadata={metadata} />}
        {auditType !== 'detailed' && auditType !== 'messaging' && (
          <p className="text-sm text-slate-400">Type d'audit inconnu : {auditType || '(vide)'}</p>
        )}
      </div>
    </div>
  );
}
