// =============================================================================
// FGA CRM - Audit : vue detaillee (rapport markdown)
// (extraite de AuditResultPanel.tsx)
// =============================================================================

import { AlertTriangle, Award, Download, ExternalLink, Lightbulb, Target } from 'lucide-react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { scoreBgColor, scoreColor } from './auditUtils';
import { CollapsibleSection, ScoreBar } from './AuditAtoms';

export function DetailedAuditView({ metadata, content }: { metadata: Record<string, unknown>; content: string }) {
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
