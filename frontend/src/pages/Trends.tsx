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
import { AlertTriangle, Play, ShieldAlert } from 'lucide-react';
import clsx from 'clsx';

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
  // Ciblage : categorie du referentiel (select) OU sujet libre (input texte).
  const [freeMode, setFreeMode] = useState(false);
  const [freeQuery, setFreeQuery] = useState('');
  const [country, setCountry] = useState('FR');
  const [timeframe, setTimeframe] = useState<TrendTimeframe>('today 12-m');
  const [mode, setMode] = useState<TrendMode>('quick');
  const [seedsInput, setSeedsInput] = useState('');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Bascule categorie <-> sujet libre : reset du job/erreur pour repartir propre.
  const switchTargetMode = (free: boolean) => {
    setFreeMode(free);
    setActiveJobId(null);
    setErrorMsg(null);
  };

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
    // Pas de "dernier rapport" en mode sujet libre (non rattache a une categorie).
    enabled: hasAccess && !!effectiveCategoryId && !activeJobId && !freeMode,
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
  const { data: jobReport, isError: jobReportError } = useQuery({
    queryKey: ['trend-report', activeJobId],
    queryFn: () => getTrendReport(activeJobId as string),
    enabled: !!activeJobId && job?.status === 'completed',
  });

  // ---- Mutation : lancer une analyse ----
  const runMutation = useMutation({
    mutationFn: () => {
      const base = {
        mode,
        country,
        language: 'fr',
        timeframe,
        seed_terms: seedsInput.split(',').map((s) => s.trim()).filter(Boolean),
      };
      // Sujet libre -> `query` ; sinon categorie du referentiel -> `category_id`.
      return createTrendReport(
        freeMode
          ? { ...base, query: freeQuery.trim() }
          : { ...base, category_id: effectiveCategoryId },
      );
    },
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

  // Etat "occupe" : couvre la fenetre du POST de creation (runMutation.isPending)
  // ET la vie du job. Sans ca, l'utilisateur ne voyait qu'un bouton grise pendant
  // le POST (mode rapide = inline, plusieurs sec).
  const isSubmitting = runMutation.isPending;
  // Le job est "regle" quand il a echoue, ou qu'il est complete ET que son rapport
  // est charge (ou son chargement en erreur). Rester occupe jusque-la evite un
  // flash d'etat vide entre 'completed' et l'affichage effectif du rapport.
  const jobSettled =
    job?.status === 'failed' ||
    (job?.status === 'completed' && (!!jobReport || jobReportError));
  const isBusy = isSubmitting || (!!activeJobId && !jobSettled);
  const isFailed = job?.status === 'failed';
  // Lancement possible : sujet libre non vide, ou categorie selectionnee.
  const canLaunch = freeMode ? freeQuery.trim().length > 0 : !!effectiveCategoryId;
  // Rapport a afficher : job actif complete, sinon dernier rapport connu (seulement
  // en mode categorie — un sujet libre n'a pas d'historique par categorie).
  const report: TrendReport | null =
    jobReport ?? (activeJobId || freeMode ? null : latestReport) ?? null;

  return (
    <div className="px-8 py-7 space-y-6">
      <PageHeader />

      {/* ===== Bandeau de filtres ===== */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            {/* Bascule categorie du referentiel <-> sujet libre */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-700">Cible</span>
              <div className="flex items-center gap-0.5 rounded-md bg-slate-100 p-0.5">
                {([['Categorie', false], ['Sujet libre', true]] as const).map(([label, free]) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => switchTargetMode(free)}
                    className={clsx(
                      'px-2 py-0.5 text-[11px] rounded transition-colors',
                      freeMode === free
                        ? 'bg-white text-slate-700 shadow-sm'
                        : 'text-slate-500 hover:text-slate-700',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {freeMode ? (
              <input
                value={freeQuery}
                onChange={(e) => setFreeQuery(e.target.value)}
                placeholder="prospection IA, RevOps…"
                aria-label="Sujet libre a analyser"
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none min-w-[200px]"
              />
            ) : (
              <select
                value={effectiveCategoryId}
                onChange={(e) => { setCategoryId(e.target.value); setActiveJobId(null); }}
                disabled={catLoading || categories.length === 0}
                aria-label="Categorie"
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none min-w-[200px]"
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.label}</option>
                ))}
              </select>
            )}
          </div>

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
            loading={isBusy}
            icon={Play}
            onClick={() => runMutation.mutate()}
            disabled={!canLaunch || isBusy}
          >
            {isBusy ? 'Analyse en cours…' : "Lancer l'analyse"}
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
      {isBusy && <RunningState mode={job?.mode ?? mode} />}
      {isFailed && <FailedState error={job?.error ?? null} />}

      {!isBusy && !isFailed && !report && (
        <EmptyState categories={categories.length} />
      )}

      {/* ===== Rapport ===== */}
      {!isBusy && !isFailed && report && report.signals && (
        <ReportView report={report} />
      )}
    </div>
  );
}

