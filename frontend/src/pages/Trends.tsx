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
import { AlertTriangle, Loader2, Play, ShieldAlert } from 'lucide-react';

import { useAuth } from '../contexts/useAuth';
import { isManagerOrAbove } from '../types';
import {
  listTrendCategories, createTrendReport, getTrendJob, getTrendReport,
  getLatestTrendReport,
} from '../api/trends';
import type { TrendMode, TrendTimeframe, TrendReport } from '../types/trends';
import { Button } from '../components/ui';
import { ReportView } from '../components/trends/TrendReportView';
import {
  EmptyState, FailedState, Field, PageHeader, RunningState, SelectMini,
} from '../components/trends/TrendStates';
import {
  COUNTRIES, JOB_POLL_INTERVAL, MODES, TIMEFRAMES, extractError,
} from '../components/trends/trendUtils';

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

