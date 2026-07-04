// =============================================================================
// FGA CRM - GEO : rendu du tableau de bord (extrait de GEO.tsx)
// =============================================================================
// Bloc de rendu pur du dashboard GEO : FilterBar (marque / moteur / periode),
// bandeaux de feedback, alertes, KPI, gaps, evolution SoV/Visibilite, rankings
// et health moteurs. Recoit les donnees et handlers en props — aucun hook de
// data ici (le shell GEO.tsx conserve queries/mutations/modales).
// =============================================================================

import {
  Activity, TrendingUp, Eye, Star, AlertTriangle, CheckCircle, XCircle,
  Play, RefreshCw, Plus, MessageSquarePlus,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import clsx from 'clsx';

import type {
  GeoAlert, GeoBrand, GeoBrandOverview, GeoEngine, GeoGap, GeoHealth, GeoPrompt,
  GeoDashboard as GeoDashboardData,
} from '../../types/geo';
import { Button } from '../ui';
import { BrandSelector } from './BrandSelector';
import { GapRow, KpiTile, RankList } from './GeoAtoms';
import {
  COLOR_SOV, COLOR_VISIBILITY, ENGINES, PERIODS,
  avgMetric, formatRate, sentimentLabel,
} from './geoUtils';

interface GeoDashboardProps {
  // ---- Donnees ----
  brands: GeoBrand[];
  brandsOverview: GeoBrandOverview[];
  activeBrandId: string;
  selectedEngine: GeoEngine;
  period: '7' | '30' | '90';
  canWrite: boolean;
  prompts: GeoPrompt[];
  dashboard: GeoDashboardData | undefined;
  dashLoading: boolean;
  gaps: GeoGap[];
  gapsLoading: boolean;
  alerts: GeoAlert[];
  health: GeoHealth[];
  successMsg: string | null;
  errorMsg: string | null;
  remeasurePending: boolean;
  // ---- Handlers ----
  onSelectBrand: (id: string) => void;
  setSelectedEngine: (engine: GeoEngine) => void;
  setPeriod: (period: '7' | '30' | '90') => void;
  onOpenPrompts: () => void;
  onOpenBrandModal: () => void;
  onOpenRunModal: () => void;
  onRemeasure: () => void;
  onDismissSuccess: () => void;
  onDismissError: () => void;
}

export function GeoDashboard({
  brands,
  brandsOverview,
  activeBrandId,
  selectedEngine,
  period,
  canWrite,
  prompts,
  dashboard,
  dashLoading,
  gaps,
  gapsLoading,
  alerts,
  health,
  successMsg,
  errorMsg,
  remeasurePending,
  onSelectBrand,
  setSelectedEngine,
  setPeriod,
  onOpenPrompts,
  onOpenBrandModal,
  onOpenRunModal,
  onRemeasure,
  onDismissSuccess,
  onDismissError,
}: GeoDashboardProps) {
  const metrics = dashboard?.metrics ?? [];
  const hasActiveAlerts = alerts.some(
    (a) => a.severity === 'critical' || a.severity === 'warning',
  );

  // Donnees du LineChart, triees par jour
  const chartData = [...metrics]
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((m) => ({
      date: m.day,
      sov: m.sov ?? 0,
      visibility: m.visibility_rate ?? 0,
    }));

  // KPI agreges
  const kVisibility = avgMetric(metrics, 'visibility_rate');
  const kSov = avgMetric(metrics, 'sov');
  const kSovWeighted = avgMetric(metrics, 'sov_weighted');
  const kSentiment = avgMetric(metrics, 'sentiment_avg');

  return (
    <>
      {/* ===== FilterBar : Brand tabs | Engine | Periode ===== */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Selecteur de marque : dropdown recherchable + mini-score */}
        <BrandSelector
          brands={brandsOverview}
          fallbackName={brands.find((b) => b.id === activeBrandId)?.name ?? null}
          activeBrandId={activeBrandId}
          onSelect={(id) => onSelectBrand(id)}
          canWrite={canWrite}
          onAddBrand={onOpenBrandModal}
        />

        <div className="h-5 w-px bg-slate-200" aria-hidden />

        {/* Engine selector */}
        <div className="flex items-center gap-1 flex-wrap">
          {ENGINES.map((e) => {
            const h = health.find((x) => x.engine === e.value);
            const unconfigured = h?.status === 'unconfigured';
            return (
              <button
                key={e.value}
                type="button"
                onClick={() => setSelectedEngine(e.value)}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors inline-flex items-center gap-1.5',
                  e.value === selectedEngine
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700',
                )}
              >
                {e.label}
                {unconfigured && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-slate-200 text-slate-500">
                    Non configure
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="h-5 w-px bg-slate-200" aria-hidden />

        {/* Periode */}
        <label className="sr-only" htmlFor="geo-period">Periode</label>
        <select
          id="geo-period"
          value={period}
          onChange={(e) => setPeriod(e.target.value as '7' | '30' | '90')}
          className="px-3 py-1.5 rounded-lg text-sm border border-slate-200 text-slate-700 bg-white"
        >
          {PERIODS.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>

        {/* Actions (admin only) */}
        {canWrite && (
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={MessageSquarePlus}
              onClick={onOpenPrompts}
            >
              Prompts ({prompts.length})
            </Button>
            <Button variant="secondary" size="sm" icon={Plus} onClick={onOpenBrandModal}>
              Marque
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={Play}
              disabled={prompts.length === 0}
              title={prompts.length === 0 ? 'Aucun prompt a mesurer' : undefined}
              onClick={onOpenRunModal}
            >
              Lancer un run
            </Button>
          </div>
        )}
      </div>

      {/* ===== Bandeaux de feedback mutation ===== */}
      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-emerald-800 flex-1">{successMsg}</p>
          <button
            type="button"
            onClick={onDismissSuccess}
            className="text-emerald-500 hover:text-emerald-700"
            aria-label="Fermer"
          >
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-800 flex-1">{errorMsg}</p>
          <button
            type="button"
            onClick={onDismissError}
            className="text-red-500 hover:text-red-700"
            aria-label="Fermer"
          >
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ===== Alert banner (P3) ===== */}
      {hasActiveAlerts && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">
              {alerts.length} alerte(s) detectee(s)
            </p>
            {alerts.slice(0, 3).map((a, i) => (
              <p key={i} className="text-xs text-amber-700 mt-1">• {a.message}</p>
            ))}
          </div>
        </div>
      )}

      {/* ===== Contenu principal : depend du chargement dashboard ===== */}
      {dashLoading ? (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 text-center text-sm text-slate-500">
          Chargement du tableau de bord...
        </div>
      ) : (
        <>
          {/* ===== KPI Strip (4 colonnes) ===== */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiTile label="Visibilite" value={formatRate(kVisibility)} icon={Eye} color="text-blue-600" bg="bg-blue-50" />
            <KpiTile label="Share of Voice" value={formatRate(kSov)} icon={Activity} color="text-indigo-600" bg="bg-indigo-50" />
            <KpiTile label="SoV pondere" value={formatRate(kSovWeighted)} icon={TrendingUp} color="text-violet-600" bg="bg-violet-50" />
            <KpiTile label="Sentiment" value={sentimentLabel(kSentiment)} icon={Star} color="text-amber-600" bg="bg-amber-50" />
          </div>

          {/* ===== Gaps a traiter (P4) — juste sous les KPI ===== */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <AlertTriangle className="w-3.5 h-3.5 text-slate-400" />
                Gaps a traiter
                <span className="text-xs text-slate-400 tabular-nums font-normal">· {gaps.length}</span>
              </div>
              {canWrite && gaps.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  loading={remeasurePending}
                  onClick={onRemeasure}
                >
                  Declencher re-mesure
                </Button>
              )}
            </div>

            {gapsLoading ? (
              <div className="py-8 text-center text-sm text-slate-400">Chargement des gaps...</div>
            ) : gaps.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-400">
                Aucun gap detecte sur la periode — la marque est bien positionnee.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                      <th className="px-4 py-2 font-medium">Prompt</th>
                      <th className="px-4 py-2 font-medium">Intention</th>
                      <th className="px-4 py-2 font-medium">Priorite</th>
                      <th className="px-4 py-2 font-medium">Visibilite</th>
                      <th className="px-4 py-2 font-medium">Suggestion d'action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {gaps.map((g) => (
                      <GapRow key={g.prompt_id} gap={g} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ===== Grid 2/3 main (chart) + 1/3 side (sources/concurrents) ===== */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main : LineChart SoV / Visibilite (self-start : ne s'etire pas
                a la hauteur de la colonne laterale, evite le grand vide) */}
            <div className="lg:col-span-2 self-start bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 text-sm font-semibold text-slate-800">
                <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
                Evolution SoV / Visibilite
              </div>
              <div className="px-4 py-4">
                {chartData.length === 0 ? (
                  <div className="h-[200px] flex items-center justify-center text-sm text-slate-400">
                    Aucune metrique sur la periode
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line type="monotone" dataKey="sov" name="SoV" stroke={COLOR_SOV} strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="visibility" name="Visibilite" stroke={COLOR_VISIBILITY} strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* Side : Top sources + Top concurrents */}
            <div className="space-y-6">
              <RankList
                title="Top sources"
                icon={Activity}
                items={(dashboard?.top_sources ?? []).map((s) => ({ label: s.domain, count: s.count }))}
                emptyLabel="Aucune source citee"
              />
              <RankList
                title="Top concurrents"
                icon={Star}
                items={(dashboard?.top_competitors ?? []).map((c) => ({ label: c.nom, count: c.mentions }))}
                emptyLabel="Aucun concurrent detecte"
              />
            </div>
          </div>
        </>
      )}

      {/* ===== Health moteurs (admin only) ===== */}
      {canWrite && health.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 text-sm font-semibold text-slate-800">
            <CheckCircle className="w-3.5 h-3.5 text-slate-400" />
            Health moteurs
          </div>
          <div className="p-4 flex flex-wrap gap-2">
            {health.map((h) => (
              <div
                key={h.engine}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200"
                title={h.error ?? undefined}
              >
                {h.status === 'ok' ? (
                  <CheckCircle className="w-4 h-4 text-emerald-500" />
                ) : h.status === 'error' ? (
                  <XCircle className="w-4 h-4 text-red-500" />
                ) : (
                  <div className="w-4 h-4 rounded-full bg-slate-300" />
                )}
                <span className="text-xs text-slate-700">{h.engine}</span>
                <span
                  className={clsx(
                    'text-xs',
                    h.status === 'ok'
                      ? 'text-emerald-600'
                      : h.status === 'error'
                        ? 'text-red-500'
                        : 'text-slate-400',
                  )}
                >
                  {h.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
