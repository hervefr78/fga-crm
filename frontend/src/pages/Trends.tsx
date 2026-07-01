// =============================================================================
// FGA CRM - Trends (signal de demande de marche)
// =============================================================================
// Lecture de la demande de marche par categorie/pays/periode (Google Trends via
// DataForSEO, ou provider mock si aucune cle). Deux modes : Rapide (inline) et
// Profonde (job Celery + polling).
//
// RBAC : admin + manager uniquement (les sales recoivent un ecran "non autorise").
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  TrendingUp, TrendingDown, Minus, Sparkles, Search, MapPin,
  ShieldAlert, Play, Loader2, AlertTriangle, Gauge,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import clsx from 'clsx';

import { useAuth } from '../contexts/useAuth';
import { isManagerOrAbove } from '../types';
import {
  listTrendCategories, createTrendReport, getTrendJob, getTrendReport,
  getLatestTrendReport,
} from '../api/trends';
import type {
  TrendMode, TrendTimeframe, TrendReport, MarketPulse,
} from '../types/trends';
import { Button } from '../components/ui';

// -----------------------------------------------------------------------------
// Constantes
// -----------------------------------------------------------------------------

const JOB_POLL_INTERVAL = 2000; // ms — polling d'un job deep en cours

const TIMEFRAMES: { value: TrendTimeframe; label: string }[] = [
  { value: 'now 7-d', label: '7 jours' },
  { value: 'today 1-m', label: '1 mois' },
  { value: 'today 3-m', label: '3 mois' },
  { value: 'today 12-m', label: '12 mois' },
  { value: 'today 5-y', label: '5 ans' },
];

const MODES: { value: TrendMode; label: string }[] = [
  { value: 'quick', label: 'Rapide' },
  { value: 'deep', label: 'Profonde' },
];

const COUNTRIES: { value: string; label: string }[] = [
  { value: 'FR', label: 'France' },
  { value: 'BE', label: 'Belgique' },
  { value: 'CH', label: 'Suisse' },
  { value: 'CA', label: 'Canada' },
];

const DIRECTION_META: Record<
  MarketPulse['direction'],
  { label: string; icon: React.ElementType; color: string }
> = {
  up: { label: 'En hausse', icon: TrendingUp, color: 'text-emerald-600' },
  down: { label: 'En baisse', icon: TrendingDown, color: 'text-red-500' },
  flat: { label: 'Stable', icon: Minus, color: 'text-slate-400' },
};

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

function formatScore(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toFixed(1);
}

function formatGrowth(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `+${value.toFixed(0)} %`;
}

function extractError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = resp?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}

// =============================================================================
// Page
// =============================================================================

export default function TrendsPage() {
  const { user } = useAuth();
  const hasAccess = isManagerOrAbove(user);

  // ---- Etats de configuration ----
  const [categoryId, setCategoryId] = useState<string>('');
  const [country, setCountry] = useState('FR');
  const [timeframe, setTimeframe] = useState<TrendTimeframe>('today 12-m');
  const [mode, setMode] = useState<TrendMode>('quick');
  const [seedsInput, setSeedsInput] = useState('');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // ---- Queries ----
  const { data: categories = [], isLoading: catLoading } = useQuery({
    queryKey: ['trend-categories'],
    queryFn: listTrendCategories,
    enabled: hasAccess,
  });

  const effectiveCategoryId = categoryId || categories[0]?.id || '';

  // Dernier rapport connu pour la categorie (affiche tant qu'aucun job actif).
  const { data: latestReport } = useQuery({
    queryKey: ['trend-latest', effectiveCategoryId, country],
    queryFn: () => getLatestTrendReport(effectiveCategoryId, country),
    enabled: hasAccess && !!effectiveCategoryId && !activeJobId,
    retry: false,
  });

  // Statut du job actif (polling si en cours).
  const { data: job } = useQuery({
    queryKey: ['trend-job', activeJobId],
    queryFn: () => getTrendJob(activeJobId as string),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'queued' || s === 'running' ? JOB_POLL_INTERVAL : false;
    },
  });

  // Rapport du job actif (une fois complete).
  const { data: jobReport } = useQuery({
    queryKey: ['trend-report', activeJobId],
    queryFn: () => getTrendReport(activeJobId as string),
    enabled: !!activeJobId && job?.status === 'completed',
  });

  // ---- Mutation : lancer une analyse ----
  const runMutation = useMutation({
    mutationFn: () =>
      createTrendReport({
        mode,
        category_id: effectiveCategoryId,
        country,
        language: 'fr',
        timeframe,
        seed_terms: seedsInput.split(',').map((s) => s.trim()).filter(Boolean),
      }),
    onSuccess: (createdJob) => {
      setErrorMsg(null);
      setActiveJobId(createdJob.job_id);
    },
    onError: (err: unknown) => {
      setErrorMsg(extractError(err, "Echec du lancement de l'analyse."));
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
            Le module Trends est reserve aux administrateurs et managers.
          </p>
        </div>
      </div>
    );
  }

  const isRunning = job?.status === 'queued' || job?.status === 'running';
  const isFailed = job?.status === 'failed';
  // Rapport a afficher : job actif complete, sinon dernier rapport connu.
  const report: TrendReport | null = jobReport ?? (activeJobId ? null : latestReport) ?? null;

  return (
    <div className="px-8 py-7 space-y-6">
      <PageHeader />

      {/* ===== Bandeau de filtres ===== */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Categorie">
            <select
              value={effectiveCategoryId}
              onChange={(e) => { setCategoryId(e.target.value); setActiveJobId(null); }}
              disabled={catLoading || categories.length === 0}
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none min-w-[200px]"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </Field>

          <Field label="Pays">
            <SelectMini value={country} onChange={setCountry} options={COUNTRIES} />
          </Field>

          <Field label="Periode">
            <SelectMini
              value={timeframe}
              onChange={(v) => setTimeframe(v as TrendTimeframe)}
              options={TIMEFRAMES}
            />
          </Field>

          <Field label="Mode">
            <SelectMini
              value={mode}
              onChange={(v) => setMode(v as TrendMode)}
              options={MODES}
            />
          </Field>

          <Field label="Seeds (optionnel, separes par des virgules)">
            <input
              value={seedsInput}
              onChange={(e) => setSeedsInput(e.target.value)}
              placeholder="prospection, sales automation"
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none min-w-[240px]"
            />
          </Field>

          <Button
            variant="primary"
            size="sm"
            icon={isRunning || runMutation.isPending ? Loader2 : Play}
            onClick={() => runMutation.mutate()}
            disabled={!effectiveCategoryId || isRunning || runMutation.isPending}
          >
            {isRunning ? 'Analyse en cours…' : "Lancer l'analyse"}
          </Button>
        </div>
      </div>

      {/* ===== Messages ===== */}
      {errorMsg && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ===== Etats ===== */}
      {isRunning && <RunningState mode={job?.mode ?? mode} />}
      {isFailed && <FailedState error={job?.error ?? null} />}

      {!isRunning && !isFailed && !report && (
        <EmptyState categories={categories.length} />
      )}

      {/* ===== Rapport ===== */}
      {!isRunning && !isFailed && report && report.signals && (
        <ReportView report={report} />
      )}
    </div>
  );
}

// =============================================================================
// Sous-composants
// =============================================================================

function PageHeader() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-800">
        Trends — Signal de marche
      </h1>
      <p className="text-sm text-slate-500 mt-1">
        Lecture de la demande de recherche par categorie, pays et periode. Indice
        d&apos;interet relatif (0-100), pas un volume absolu.
      </p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function SelectMini({
  value, onChange, options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

function RunningState({ mode }: { mode: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
      <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
      <p className="text-sm text-slate-600">
        Analyse {mode === 'deep' ? 'profonde' : 'rapide'} en cours…
      </p>
      <p className="text-xs text-slate-400">Le rapport s&apos;affichera automatiquement.</p>
    </div>
  );
}

function FailedState({ error }: { error: string | null }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
      <div className="w-12 h-12 rounded-lg bg-red-50 flex items-center justify-center">
        <AlertTriangle className="w-6 h-6 text-red-500" />
      </div>
      <p className="text-sm text-slate-600">L&apos;analyse a echoue.</p>
      {error && <p className="text-xs text-slate-400 max-w-md">{error}</p>}
    </div>
  );
}

function EmptyState({ categories }: { categories: number }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
      <div className="w-12 h-12 rounded-lg bg-slate-50 flex items-center justify-center">
        <Search className="w-6 h-6 text-slate-400" />
      </div>
      <p className="text-sm text-slate-500 max-w-sm">
        {categories === 0
          ? 'Aucune categorie disponible pour le moment.'
          : "Choisissez une categorie et lancez une analyse pour afficher les tendances."}
      </p>
    </div>
  );
}

function ReportView({ report }: { report: TrendReport }) {
  const s = report.signals!;
  const meta = report.meta;
  const pulse = s.market_pulse;
  const dir = DIRECTION_META[pulse.direction];
  const breakoutCount = s.rising_queries.filter((q) => q.breakout).length;

  const chartData = s.timeseries.map((p) => ({ date: p.date, value: p.value }));

  return (
    <div className="space-y-6">
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

      {/* Market pulse chart */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 text-sm font-semibold text-slate-800">
          Interet dans le temps
        </div>
        <div className="p-4">
          {chartData.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-400">Pas de serie disponible</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} minTickGap={40} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Line type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

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
  icon: React.ElementType;
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
