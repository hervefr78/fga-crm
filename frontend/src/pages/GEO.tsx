// =============================================================================
// FGA CRM - GEO Dashboard (Generative Engine Optimization)
// =============================================================================
// Mesure la visibilite des marques dans les moteurs IA (ChatGPT, Perplexite...)
// et detecte les gaps pour alimenter la boucle d'optimisation P4.
//
// RBAC : admin + manager uniquement (les sales recoivent un ecran "non autorise").
// Les actions d'ecriture (trigger run, remeasure) sont reservees aux admins.
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity, TrendingUp, Eye, Star, AlertTriangle, CheckCircle, XCircle,
  Play, RefreshCw, ShieldAlert,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import clsx from 'clsx';

import { useAuth } from '../contexts/useAuth';
import { isAdmin, isManagerOrAbove } from '../types';
import {
  listGeoBrands, getGeoDashboard, getGeoGaps, getGeoAlerts,
  getGeoHealth, listGeoPrompts, triggerGeoRun, triggerGeoRemeasure,
} from '../api/geo';
import type { GeoEngine, GeoGap, GeoMetricsDaily } from '../types/geo';
import { Button, Modal } from '../components/ui';

// -----------------------------------------------------------------------------
// Constantes
// -----------------------------------------------------------------------------

// Moteurs presentes dans le selecteur (sous-ensemble collectable — cf backend P1/P2)
const ENGINES: { value: GeoEngine; label: string }[] = [
  { value: 'perplexity', label: 'Perplexity' },
  { value: 'openai', label: 'ChatGPT' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'google_aio', label: 'Google AIO' },
];

const PERIODS: { value: '7' | '30' | '90'; label: string }[] = [
  { value: '7', label: '7 jours' },
  { value: '30', label: '30 jours' },
  { value: '90', label: '90 jours' },
];

const INTENT_COLORS: Record<string, string> = {
  informationnel: 'bg-blue-50 text-blue-700',
  comparatif: 'bg-orange-50 text-orange-700',
  transactionnel: 'bg-emerald-50 text-emerald-700',
};

const INTENT_LABELS: Record<string, string> = {
  informationnel: 'Informationnel',
  comparatif: 'Comparatif',
  transactionnel: 'Transactionnel',
};

// Couleurs des courbes (charte : indigo + emeraude, pas de gradient)
const COLOR_SOV = '#4f46e5';
const COLOR_VISIBILITY = '#10b981';

// -----------------------------------------------------------------------------
// Helpers de calcul (KPI = moyennes sur les metriques journalieres)
// -----------------------------------------------------------------------------

/** Moyenne d'un champ numerique sur les metriques, en ignorant les null. */
function avgMetric(
  metrics: GeoMetricsDaily[],
  key: 'visibility_rate' | 'sov' | 'sov_weighted' | 'sentiment_avg',
): number | null {
  const values = metrics
    .map((m) => m[key])
    .filter((v): v is number => typeof v === 'number');
  if (values.length === 0) return null;
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

/** Formate un taux (0-100) en "xx.x %" ou "—" si null. */
function formatRate(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(1)} %`;
}

/** Convertit un sentiment moyen (-1..1) en label lisible, ou "—" si null. */
function sentimentLabel(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (value > 0.2) return 'Positif';
  if (value < -0.2) return 'Negatif';
  return 'Neutre';
}

// =============================================================================
// Page
// =============================================================================

export default function GEOPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // ---- Etats locaux ----
  const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);
  const [selectedEngine, setSelectedEngine] = useState<GeoEngine>('perplexity');
  const [period, setPeriod] = useState<'7' | '30' | '90'>('30');
  const [runModalOpen, setRunModalOpen] = useState(false);
  // Message de succes des mutations Celery (task_id + nb runs planifies)
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const canWrite = isAdmin(user);
  // RBAC : les sales n'ont pas acces. Le flag est evalue APRES tous les hooks
  // (rules-of-hooks) — on coupe simplement les requetes pour eux via `enabled`.
  const hasAccess = isManagerOrAbove(user);

  // ---- Queries ----
  const { data: brands = [], isLoading: brandsLoading } = useQuery({
    queryKey: ['geo-brands'],
    queryFn: () => listGeoBrands(true), // marques possedees uniquement
    enabled: hasAccess,
  });

  // Marque active : selection explicite, sinon la premiere disponible
  const activeBrandId = selectedBrandId ?? brands[0]?.id ?? null;

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['geo-dashboard', activeBrandId, selectedEngine, period],
    queryFn: () => {
      const dateTo = new Date().toISOString().slice(0, 10);
      const dateFrom = new Date(Date.now() - parseInt(period, 10) * 86400000).toISOString().slice(0, 10);
      return getGeoDashboard(activeBrandId!, selectedEngine, dateFrom, dateTo);
    },
    enabled: hasAccess && !!activeBrandId,
  });

  const { data: gaps = [], isLoading: gapsLoading } = useQuery({
    queryKey: ['geo-gaps', activeBrandId, selectedEngine, period],
    queryFn: () => getGeoGaps(activeBrandId!, selectedEngine, parseInt(period, 10)),
    enabled: hasAccess && !!activeBrandId,
    retry: false,
  });

  const { data: alerts = [] } = useQuery({
    queryKey: ['geo-alerts', activeBrandId, selectedEngine],
    queryFn: () => getGeoAlerts(activeBrandId!, selectedEngine),
    enabled: hasAccess && !!activeBrandId,
    retry: false,
  });

  // Health : admin only (le backend renvoie 403 aux managers)
  const { data: health = [] } = useQuery({
    queryKey: ['geo-health'],
    queryFn: getGeoHealth,
    enabled: isAdmin(user),
    retry: false,
  });

  const { data: prompts = [] } = useQuery({
    queryKey: ['geo-prompts', activeBrandId],
    queryFn: () => listGeoPrompts(activeBrandId!),
    enabled: hasAccess && !!activeBrandId,
  });

  // ---- Mutations ----
  const runMutation = useMutation({
    mutationFn: () =>
      triggerGeoRun({
        brand_id: activeBrandId!,
        engine: selectedEngine,
        prompt_ids: prompts.map((p) => p.id),
      }),
    onSuccess: (data) => {
      setRunModalOpen(false);
      setErrorMsg(null);
      setSuccessMsg(
        `Run planifie : ${data.runs_scheduled} mesure(s) (task ${data.task_id}).`,
      );
    },
    onError: (err: unknown) => {
      setErrorMsg(extractError(err, 'Echec du declenchement du run.'));
    },
  });

  const remeasureMutation = useMutation({
    mutationFn: () =>
      triggerGeoRemeasure(activeBrandId!, selectedEngine, parseInt(period, 10)),
    onSuccess: (data) => {
      setErrorMsg(null);
      setSuccessMsg(
        `Re-mesure planifiee : ${data.runs_scheduled} mesure(s) (task ${data.task_id}).`,
      );
      // Rafraichir les gaps apres declenchement
      void queryClient
        .invalidateQueries({ queryKey: ['geo-gaps', activeBrandId] })
        .catch((e) => console.error('[GEO] invalidate gaps', e));
    },
    onError: (err: unknown) => {
      setErrorMsg(extractError(err, 'Echec de la re-mesure.'));
    },
  });

  // ---- Garde RBAC (apres tous les hooks — rules-of-hooks) ----
  if (!hasAccess) {
    return (
      <div className="px-8 py-7">
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-red-50 flex items-center justify-center">
            <ShieldAlert className="w-6 h-6 text-red-500" />
          </div>
          <h1 className="text-lg font-semibold text-slate-800">Acces non autorise</h1>
          <p className="text-sm text-slate-500 max-w-sm">
            Le module GEO est reserve aux administrateurs et managers.
          </p>
        </div>
      </div>
    );
  }

  // ---- Etats globaux de chargement / vide ----
  if (brandsLoading) {
    return <div className="px-8 py-7 text-sm text-slate-500">Chargement...</div>;
  }

  if (!activeBrandId) {
    return (
      <div className="px-8 py-7">
        <PageHeader />
        <div className="mt-6 bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-slate-50 flex items-center justify-center">
            <Eye className="w-6 h-6 text-slate-400" />
          </div>
          <p className="text-sm text-slate-500">
            Aucune marque configuree. Ajoutez une marque possedee pour commencer le suivi GEO.
          </p>
        </div>
      </div>
    );
  }

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
    <div className="px-8 py-7 space-y-6">
      <PageHeader />

      {/* ===== FilterBar : Brand tabs | Engine | Periode ===== */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Brands (tabs) */}
        <div className="flex items-center gap-1 flex-wrap">
          {brands.map((b) => (
            <button
              key={b.id}
              type="button"
              onClick={() => setSelectedBrandId(b.id)}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                b.id === activeBrandId
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700',
              )}
            >
              {b.name}
            </button>
          ))}
        </div>

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

        {/* Action : lancer un run (admin only) */}
        {canWrite && (
          <div className="ml-auto">
            <Button
              variant="secondary"
              size="sm"
              icon={Play}
              disabled={prompts.length === 0}
              title={prompts.length === 0 ? 'Aucun prompt a mesurer' : undefined}
              onClick={() => setRunModalOpen(true)}
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
            onClick={() => setSuccessMsg(null)}
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
            onClick={() => setErrorMsg(null)}
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

          {/* ===== Grid 2/3 main (chart) + 1/3 side (sources/concurrents) ===== */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main : LineChart SoV / Visibilite */}
            <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
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

      {/* ===== Section Gaps a traiter (P4) ===== */}
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
              loading={remeasureMutation.isPending}
              onClick={() => remeasureMutation.mutate()}
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

      {/* ===== Health moteurs (admin only) ===== */}
      {isAdmin(user) && health.length > 0 && (
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

      {/* ===== Modale de confirmation : lancer un run (admin only) ===== */}
      {canWrite && (
        <Modal
          open={runModalOpen}
          onClose={() => setRunModalOpen(false)}
          title="Lancer un run GEO"
          footer={
            <>
              <Button variant="secondary" onClick={() => setRunModalOpen(false)}>
                Annuler
              </Button>
              <Button
                variant="primary"
                icon={Play}
                loading={runMutation.isPending}
                onClick={() => runMutation.mutate()}
              >
                Confirmer
              </Button>
            </>
          }
        >
          <p className="text-sm text-slate-600">
            Declencher une mesure sur le moteur{' '}
            <span className="font-medium text-slate-800">
              {ENGINES.find((e) => e.value === selectedEngine)?.label ?? selectedEngine}
            </span>{' '}
            pour les <span className="font-medium text-slate-800">{prompts.length}</span> prompt(s)
            actif(s) de cette marque.
          </p>
          <p className="text-xs text-slate-400 mt-2">
            Le traitement est asynchrone (Celery). Les resultats apparaitront une fois les mesures collectees.
          </p>
        </Modal>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Sous-composants
// -----------------------------------------------------------------------------

function PageHeader() {
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

function KpiTile({
  label, value, icon: Icon, color, bg,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
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

function RankList({
  title, icon: Icon, items, emptyLabel,
}: {
  title: string;
  icon: React.ElementType;
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

function GapRow({ gap }: { gap: GeoGap }) {
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

// -----------------------------------------------------------------------------
// Utilitaires
// -----------------------------------------------------------------------------

/** Extrait un message d'erreur lisible d'une erreur axios, avec fallback. */
function extractError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = resp?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}
