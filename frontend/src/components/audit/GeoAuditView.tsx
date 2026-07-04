// =============================================================================
// FGA CRM - Audit : vue GEO (5 layers + rapport markdown)
// (extraite de AuditResultPanel.tsx)
// =============================================================================

import { Globe } from 'lucide-react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { geoBgColor, geoScoreColor, gradeColor, scoreBarColor, scoreColor } from './auditUtils';
import { CollapsibleSection } from './AuditAtoms';

interface LayerScore {
  score: number;
  findings?: string[];
  quick_wins?: string[];
}

export function GeoAuditView({ metadata, content }: { metadata: Record<string, unknown>; content: string }) {
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
