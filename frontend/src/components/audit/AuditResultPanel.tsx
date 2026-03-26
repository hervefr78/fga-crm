// =============================================================================
// FGA CRM - Panneau de resultats d'audit Startup Radar
// Affiche les audits messaging, detailles et GEO dans la fiche entreprise
// =============================================================================

import { AlertTriangle, Award, ChevronDown, ChevronUp, Download, ExternalLink, Globe, Lightbulb, Target, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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

// Seuils GEO (/100)
function geoScoreColor(score: number): string {
  if (score >= 60) return 'text-emerald-600';
  if (score >= 40) return 'text-amber-600';
  return 'text-red-500';
}

function geoBgColor(score: number): string {
  if (score >= 60) return 'bg-emerald-50';
  if (score >= 40) return 'bg-amber-50';
  return 'bg-red-50';
}

function gradeColor(grade: string): string {
  if (grade === 'A') return 'text-emerald-600 bg-emerald-50';
  if (grade === 'B') return 'text-blue-600 bg-blue-50';
  if (grade === 'C') return 'text-amber-600 bg-amber-50';
  return 'text-red-600 bg-red-50';
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
// Radar Chart SVG — 8 axes
// ---------------------------------------------------------------------------

interface RadarAxis {
  key: string;
  value: number;
  label_fr: string;
  label_en?: string;
}

function RadarChart({ axes, size = 240 }: { axes: RadarAxis[]; size?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 30;
  const levels = 5; // Cercles concentriques (echelle 0-10, pas de 2)
  const n = axes.length;
  if (n < 3) return null;

  const angleStep = (2 * Math.PI) / n;
  // Depart en haut (-PI/2)
  const startAngle = -Math.PI / 2;

  const getPoint = (axisIndex: number, value: number, max: number = 10) => {
    const angle = startAngle + axisIndex * angleStep;
    const r = (value / max) * radius;
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  };

  // Grille concentrique
  const gridLines = Array.from({ length: levels }, (_, i) => {
    const levelRadius = ((i + 1) / levels) * radius;
    const points = Array.from({ length: n }, (_, j) => {
      const angle = startAngle + j * angleStep;
      return `${cx + levelRadius * Math.cos(angle)},${cy + levelRadius * Math.sin(angle)}`;
    });
    return points.join(' ');
  });

  // Axes (lignes du centre vers les bords)
  const axisLines = Array.from({ length: n }, (_, i) => {
    const angle = startAngle + i * angleStep;
    return {
      x2: cx + radius * Math.cos(angle),
      y2: cy + radius * Math.sin(angle),
    };
  });

  // Polygone des valeurs
  const dataPoints = axes.map((a, i) => getPoint(i, a.value));
  const dataPolygon = dataPoints.map((p) => `${p.x},${p.y}`).join(' ');

  // Labels
  const labelPositions = axes.map((a, i) => {
    const angle = startAngle + i * angleStep;
    const labelR = radius + 20;
    return {
      x: cx + labelR * Math.cos(angle),
      y: cy + labelR * Math.sin(angle),
      label: a.label_fr,
      value: a.value,
    };
  });

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[280px] mx-auto">
      {/* Grille */}
      {gridLines.map((points, i) => (
        <polygon
          key={i}
          points={points}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={i === levels - 1 ? 1.5 : 0.8}
        />
      ))}

      {/* Axes */}
      {axisLines.map((line, i) => (
        <line key={i} x1={cx} y1={cy} x2={line.x2} y2={line.y2} stroke="#cbd5e1" strokeWidth={0.5} />
      ))}

      {/* Polygone des valeurs */}
      <polygon
        points={dataPolygon}
        fill="rgba(99, 102, 241, 0.15)"
        stroke="#6366f1"
        strokeWidth={2}
      />

      {/* Points */}
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#6366f1" />
      ))}

      {/* Labels */}
      {labelPositions.map((lp, i) => (
        <text
          key={i}
          x={lp.x}
          y={lp.y}
          textAnchor="middle"
          dominantBaseline="middle"
          className="text-[8px] fill-slate-500"
        >
          {lp.label}
        </text>
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Vue audit messaging (simple)
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

// ---------------------------------------------------------------------------
// Vue audit detaille (rapport markdown)
// ---------------------------------------------------------------------------

function DetailedAuditView({ metadata, content }: { metadata: Record<string, unknown>; content: string }) {
  const totalScore = (metadata.total_score as number) ?? 0;
  const interpretation = (metadata.score_interpretation as string) ?? '';
  const keyFindings = (metadata.key_findings as string[]) ?? [];
  const topPriority = (metadata.top_priority as string) ?? '';
  const scoring = (metadata.scoring as Record<string, unknown>) ?? {};
  const gapsCount = (metadata.gaps_count as number) ?? 0;
  const recsCount = (metadata.recommendations_count as number) ?? 0;
  const fileMdUrl = (metadata.file_md_url as string) ?? '';
  const fileDocxUrl = (metadata.file_docx_url as string) ?? '';
  const presentationSlug = (metadata.presentation_slug as string) ?? '';

  // Detecter si content est le rapport complet (markdown) ou juste l'interpretation
  const hasFullReport = content.length > 500;

  return (
    <div className="space-y-4">
      {/* Score principal + liens */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className={clsx('rounded-lg p-4 flex items-center gap-4', scoreBgColor(totalScore))}>
          <div className={clsx('text-4xl font-bold', scoreColor(totalScore))}>{totalScore}<span className="text-lg text-slate-400">/75</span></div>
          <div>
            <p className="text-sm font-medium text-slate-700">Score global</p>
            {interpretation && <p className="text-sm text-slate-500 mt-0.5">{interpretation}</p>}
          </div>
        </div>

        {/* Liens telechargement + presentation */}
        <div className="flex flex-wrap gap-2">
          {fileDocxUrl && (
            <a
              href={fileDocxUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              DOCX
            </a>
          )}
          {fileMdUrl && (
            <a
              href={fileMdUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Markdown
            </a>
          )}
          {presentationSlug && (
            <a
              href={`https://startupradar.fast-growth.fr/p/${presentationSlug}.html`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Presentation
            </a>
          )}
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

      {/* Key findings (si pas de rapport complet) */}
      {!hasFullReport && keyFindings.length > 0 && (
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

      {/* Scoring breakdown (si pas de rapport complet) */}
      {!hasFullReport && Object.keys(scoring).length > 0 && (
        <CollapsibleSection title="Scores par categorie" icon={Award}>
          <div className="space-y-3">
            {Object.entries(scoring).map(([key, value]) => {
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

      {/* Rapport markdown complet */}
      {hasFullReport && (
        <CollapsibleSection title="Rapport complet" icon={Award} defaultOpen={true}>
          <div className="prose prose-sm prose-slate max-w-none prose-table:border-collapse prose-th:border prose-th:border-slate-200 prose-th:bg-slate-50 prose-th:px-3 prose-th:py-1.5 prose-th:text-left prose-th:text-xs prose-th:font-semibold prose-th:text-slate-600 prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-1.5 prose-td:text-sm prose-headings:text-slate-800 prose-p:text-slate-600 prose-strong:text-slate-800 prose-li:text-slate-600">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vue audit GEO
// ---------------------------------------------------------------------------

interface LayerScore {
  score: number;
  findings?: string[];
  quick_wins?: string[];
}

function GeoAuditView({ metadata, content }: { metadata: Record<string, unknown>; content: string }) {
  const totalScore = (metadata.total_score as number) ?? 0;
  const grade = (metadata.grade as string) ?? '';
  const summary = (metadata.summary as string) ?? '';
  const contentClarity = metadata.content_clarity as LayerScore | undefined;
  const semanticHtml = metadata.semantic_html as LayerScore | undefined;
  const schemaOrg = metadata.schema_org as LayerScore | undefined;
  const crawlDirectives = metadata.crawl_directives as LayerScore | undefined;
  const agentComprehension = metadata.agent_comprehension as LayerScore | undefined;

  const hasFullReport = content.length > 500;

  const layers = [
    { label: 'Content Clarity', data: contentClarity, max: 20 },
    { label: 'Semantic HTML', data: semanticHtml, max: 20 },
    { label: 'Schema.org', data: schemaOrg, max: 20 },
    { label: 'Crawl Directives', data: crawlDirectives, max: 20 },
    { label: 'Agent Comprehension', data: agentComprehension, max: 20 },
  ];

  return (
    <div className="space-y-4">
      {/* Score + Grade */}
      <div className="flex items-center gap-4">
        <div className={clsx('rounded-lg p-4 flex items-center gap-4', geoBgColor(totalScore))}>
          <div className={clsx('text-4xl font-bold', geoScoreColor(totalScore))}>{totalScore}<span className="text-lg text-slate-400">/100</span></div>
          <div>
            <p className="text-sm font-medium text-slate-700">Score GEO</p>
            {summary && <p className="text-sm text-slate-500 mt-0.5 max-w-md">{summary.slice(0, 120)}{summary.length > 120 ? '...' : ''}</p>}
          </div>
        </div>
        {grade && (
          <div className={clsx('text-3xl font-bold px-4 py-2 rounded-lg', gradeColor(grade))}>
            {grade}
          </div>
        )}
      </div>

      {/* 5 layers */}
      <div className="space-y-3">
        {layers.map(({ label, data, max }) => {
          if (!data) return null;
          const score = data.score ?? 0;
          const pct = Math.round((score / max) * 100);
          return (
            <div key={label}>
              <div className="flex items-center gap-3 mb-1">
                <span className="text-sm text-slate-600 w-40 flex-shrink-0">{label}</span>
                <div className="flex-1 bg-slate-100 rounded-full h-2.5">
                  <div
                    className={clsx('h-2.5 rounded-full transition-all duration-500', scoreBarColor(pct))}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className={clsx('text-sm font-semibold w-12 text-right', scoreColor(pct))}>
                  {score}/{max}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Rapport markdown complet */}
      {hasFullReport && (
        <CollapsibleSection title="Rapport complet" icon={Globe} defaultOpen={true}>
          <div className="prose prose-sm prose-slate max-w-none prose-table:border-collapse prose-th:border prose-th:border-slate-200 prose-th:bg-slate-50 prose-th:px-3 prose-th:py-1.5 prose-th:text-left prose-th:text-xs prose-th:font-semibold prose-th:text-slate-600 prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-1.5 prose-td:text-sm prose-headings:text-slate-800 prose-p:text-slate-600 prose-strong:text-slate-800 prose-li:text-slate-600">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
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
  content?: string;
}

export default function AuditResultPanel({ metadata, subject, createdAt, content = '' }: AuditResultPanelProps) {
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
        {auditType === 'detailed' && <DetailedAuditView metadata={metadata} content={content} />}
        {auditType === 'messaging' && <MessagingAuditView metadata={metadata} />}
        {auditType === 'geo' && <GeoAuditView metadata={metadata} content={content} />}
        {!['detailed', 'messaging', 'geo'].includes(auditType) && (
          <p className="text-sm text-slate-400">Type d'audit inconnu : {auditType || '(vide)'}</p>
        )}
      </div>
    </div>
  );
}

// Export des sous-composants pour usage direct dans les sous-tabs
export { MessagingAuditView, DetailedAuditView, GeoAuditView, RadarChart };
export type { RadarAxis };
