// =============================================================================
// FGA CRM - Trends : rendu du rapport (extrait de Trends.tsx)
// =============================================================================

import type { ElementType } from 'react';
import { Gauge, MapPin, Search, Sparkles, TrendingUp } from 'lucide-react';
import clsx from 'clsx';

import type { TrendReport } from '../../types/trends';
import { DIRECTION_META, formatGrowth, formatScore } from './trendUtils';
import { TrendRecommendationsCard } from './TrendRecommendationsCard';
import { TrendInterestChart } from './TrendInterestChart';

export function ReportView({ report }: { report: TrendReport }) {
  const s = report.signals!;
  const meta = report.meta;
  const pulse = s.market_pulse;
  const dir = DIRECTION_META[pulse.direction];
  const breakoutCount = s.rising_queries.filter((q) => q.breakout).length;

  return (
    <div className="space-y-6">
      {/* Recommandations IA (mode Profond) — en tete si presentes */}
      {report.recommendations && (
        <TrendRecommendationsCard reco={report.recommendations} />
      )}

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile
          label="Score d'opportunite"
          value={`${formatScore(report.opportunity_score)}`}
          suffix="/100"
          icon={Gauge}
          color="text-primary-600"
          bg="bg-primary-50"
        />
        <KpiTile
          label="Indice d'interet"
          value={pulse.interest_index.toFixed(1)}
          icon={TrendingUp}
          color="text-indigo-600"
          bg="bg-indigo-50"
        />
        <KpiTile
          label="Direction"
          value={dir.label}
          icon={dir.icon}
          color={dir.color}
          bg="bg-slate-50"
        />
        <KpiTile
          label="Requetes en hausse"
          value={`${s.rising_queries.length}`}
          suffix={breakoutCount > 0 ? `dont ${breakoutCount} breakout` : undefined}
          icon={Sparkles}
          color="text-violet-600"
          bg="bg-violet-50"
        />
      </div>

      {/* Interet dans le temps (graphique interactif : detail d'un point au clic) */}
      <TrendInterestChart timeseries={s.timeseries} />

      {/* Rising / Top queries */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <QueryList
          title="Requetes en hausse"
          icon={TrendingUp}
          items={s.rising_queries.map((q) => ({
            label: q.query,
            meta: formatGrowth(q.growth),
            breakout: q.breakout,
          }))}
          emptyLabel="Aucune requete en hausse"
        />
        <QueryList
          title="Requetes dominantes"
          icon={Search}
          items={s.top_queries.map((q) => ({ label: q.query, meta: `${q.value}` }))}
          emptyLabel="Aucune requete dominante"
        />
      </div>

      {/* Regions / Topics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <QueryList
          title="Regions les plus actives"
          icon={MapPin}
          items={s.regions.map((r) => ({ label: r.region, meta: `${r.value}` }))}
          emptyLabel="Pas de signal regional"
        />
        {s.related_topics.length > 0 && (
          <QueryList
            title="Sujets connexes"
            icon={Sparkles}
            items={s.related_topics.map((t) => ({ label: t.topic, meta: `${t.value}` }))}
            emptyLabel="Aucun sujet connexe"
          />
        )}
      </div>

      {/* Methodologie */}
      {meta && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
          <div className="text-sm font-semibold text-slate-800 mb-2">Methodologie</div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
            <span>Fournisseur : <span className="text-slate-700">{meta.provider_effective}</span></span>
            <span>Periode : <span className="text-slate-700">{meta.timeframe}</span></span>
            <span>Pays : <span className="text-slate-700">{meta.country}</span></span>
            <span>
              Fraicheur : {' '}
              <span className={clsx(meta.cached ? 'text-amber-600' : 'text-emerald-600')}>
                {meta.cached ? 'donnees en cache' : 'donnees fraiches'}
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiTile({
  label, value, suffix, icon: Icon, color, bg,
}: {
  label: string;
  value: string;
  suffix?: string;
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
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold text-slate-800 tabular-nums tracking-tight">
          {value}
        </span>
        {suffix && <span className="text-xs text-slate-400">{suffix}</span>}
      </div>
    </div>
  );
}

function QueryList({
  title, icon: Icon, items, emptyLabel,
}: {
  title: string;
  icon: ElementType;
  items: { label: string; meta: string; breakout?: boolean }[];
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
            <li key={`${it.label}-${i}`} className="flex items-center justify-between px-4 py-2.5 gap-2">
              <span className="text-sm text-slate-700 truncate flex items-center gap-2">
                {it.label}
                {it.breakout && (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-violet-50 text-violet-700">
                    breakout
                  </span>
                )}
              </span>
              <span className="text-xs text-slate-500 tabular-nums px-2 py-0.5 rounded bg-slate-50 shrink-0">
                {it.meta}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
