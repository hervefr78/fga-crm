// =============================================================================
// FGA CRM - GEO : composants atomiques (extraits de GEO.tsx)
// =============================================================================

import type { ElementType } from 'react';
import clsx from 'clsx';

import type { GeoGap } from '../../types/geo';
import { INTENT_COLORS, INTENT_LABELS } from './geoUtils';

export function PageHeader() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-800">
        GEO — Visibilite IA
      </h1>
      <p className="text-sm text-slate-500 mt-1">
        Suivi de la presence des marques dans les moteurs generatifs (ChatGPT, Perplexity, Gemini)
      </p>
    </div>
  );
}

export function KpiTile({
  label, value, icon: Icon, color, bg,
}: {
  label: string;
  value: string;
  icon: ElementType;
  color: string;
  bg: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">{label}</span>
        <div className={clsx('w-7 h-7 rounded-lg flex items-center justify-center', bg)}>
          <Icon className={clsx('w-4 h-4', color)} />
        </div>
      </div>
      <div className="text-2xl font-semibold text-slate-800 tabular-nums tracking-tight mt-2">
        {value}
      </div>
    </div>
  );
}

export function RankList({
  title, icon: Icon, items, emptyLabel,
}: {
  title: string;
  icon: ElementType;
  items: { label: string; count: number }[];
  emptyLabel: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 text-sm font-semibold text-slate-800">
        <Icon className="w-3.5 h-3.5 text-slate-400" />
        {title}
      </div>
      {items.length === 0 ? (
        <div className="py-6 text-center text-sm text-slate-400">{emptyLabel}</div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((it, i) => (
            <li key={`${it.label}-${i}`} className="flex items-center justify-between px-4 py-2.5">
              <span className="text-sm text-slate-700 truncate pr-2">{it.label}</span>
              <span className="text-xs text-slate-500 tabular-nums px-2 py-0.5 rounded bg-slate-50">
                {it.count}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function GapRow({ gap }: { gap: GeoGap }) {
  return (
    <tr className="hover:bg-slate-50/60">
      <td className="px-4 py-3 text-slate-800 max-w-md">
        <span className="line-clamp-2">{gap.prompt_text}</span>
      </td>
      <td className="px-4 py-3">
        <span
          className={clsx(
            'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
            INTENT_COLORS[gap.intent] ?? 'bg-slate-50 text-slate-600',
          )}
        >
          {INTENT_LABELS[gap.intent] ?? gap.intent}
        </span>
      </td>
      <td className="px-4 py-3">
        {gap.priority ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700">
            Prioritaire
          </span>
        ) : (
          <span className="text-xs text-slate-400">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-slate-700 tabular-nums">
        {gap.visibility_rate.toFixed(1)} %
      </td>
      <td className="px-4 py-3 text-slate-600 max-w-sm">
        <span className="line-clamp-2">{gap.action_suggestion}</span>
      </td>
    </tr>
  );
}
