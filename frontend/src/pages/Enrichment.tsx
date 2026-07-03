// =============================================================================
// FGA CRM - Enrichissement d'emails B2B (feature Compass)
// =============================================================================
// Source les decideurs (CTO/CPO/CMO) des editeurs de logiciels FR, resout +
// verifie leurs emails pro, cree des contacts CRM. 2 modes : a la demande (1
// societe) ou batch/ICP (filtre NAF). RBAC : admin + manager.
// =============================================================================

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Building2, Filter, List, Play, ShieldAlert } from 'lucide-react';
import clsx from 'clsx';

import { useAuth } from '../contexts/useAuth';
import { isManagerOrAbove } from '../types';
import { createEnrichmentJob, listEnrichmentJobs } from '../api/enrichment';
import type { EnrichmentJobCreateInput, EnrichmentMode } from '../types/enrichment';
import { Button } from '../components/ui';
import { EnrichmentJobsTable } from '../components/enrichment/EnrichmentJobsTable';

const JOBS_POLL_INTERVAL = 3000;
const DEFAULT_NAF = '5829C, 5829B, 5821Z';

function extractError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}

export default function EnrichmentPage() {
  const { user } = useAuth();
  const hasAccess = isManagerOrAbove(user);
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<EnrichmentMode>('company');
  const [siren, setSiren] = useState('');
  const [sirensInput, setSirensInput] = useState('');
  const [nafInput, setNafInput] = useState(DEFAULT_NAF);
  const [limit, setLimit] = useState(50);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: jobsData } = useQuery({
    queryKey: ['enrichment-jobs'],
    queryFn: () => listEnrichmentJobs(1, 20),
    enabled: hasAccess,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      // 'awaiting_results' : bulk soumis, en attente du webhook Icypeas -> continuer a poller.
      const active = new Set(['queued', 'running', 'awaiting_results']);
      return items.some((j) => active.has(j.status)) ? JOBS_POLL_INTERVAL : false;
    },
  });

  // Extrait les SIREN (9 chiffres) d'une saisie libre (retours ligne, virgules, espaces).
  const parsedSirens = sirensInput
    .split(/[\s,;]+/)
    .map((s) => s.replace(/\D/g, ''))
    .filter((s) => s.length === 9);

  const runMutation = useMutation({
    mutationFn: () => {
      const payload: EnrichmentJobCreateInput = { mode };
      if (mode === 'company') {
        payload.siren = siren.trim();
      } else if (mode === 'batch') {
        payload.sirens = parsedSirens;
      } else {
        payload.icp_filter = {
          naf_codes: nafInput.split(',').map((s) => s.trim()).filter(Boolean),
          limit,
        };
      }
      return createEnrichmentJob(payload);
    },
    onSuccess: () => {
      setErrorMsg(null);
      void queryClient.invalidateQueries({ queryKey: ['enrichment-jobs'] });
    },
    onError: (err: unknown) => setErrorMsg(extractError(err, "Echec du lancement de l'enrichissement.")),
  });

  if (!hasAccess) {
    return (
      <div className="px-8 py-7">
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-red-50 flex items-center justify-center">
            <ShieldAlert className="w-6 h-6 text-red-500" />
          </div>
          <h1 className="text-lg font-semibold text-slate-800">Acces non autorise</h1>
          <p className="text-sm text-slate-500 max-w-sm">
            L&apos;enrichissement est reserve aux administrateurs et managers.
          </p>
        </div>
      </div>
    );
  }

  const canLaunch =
    mode === 'company' ? siren.trim().length > 0
    : mode === 'batch' ? parsedSirens.length > 0
    : nafInput.trim().length > 0;

  return (
    <div className="px-8 py-7 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-800">Enrichissement</h1>
        <p className="text-sm text-slate-500 mt-1">
          Trouve et verifie les emails pro des decideurs (CTO/CPO/CMO), cree des contacts prets
          pour l&apos;outreach. Conforme RGPD (emails pro nominatifs uniquement).
        </p>
      </div>

      {/* ===== Lancement ===== */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 space-y-4">
        {/* Selecteur de mode */}
        <div className="inline-flex rounded-lg border border-slate-200 p-0.5">
          {([['company', 'A la demande', Building2], ['batch', 'Liste de SIREN', List], ['icp', 'ICP (NAF)', Filter]] as const).map(
            ([m, label, Icon]) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={clsx(
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                  mode === m ? 'bg-primary-50 text-primary-700' : 'text-slate-500 hover:text-slate-700',
                )}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ),
          )}
        </div>

        {/* Formulaire selon le mode */}
        {mode === 'company' ? (
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-700">SIREN de la societe</span>
              <input
                value={siren}
                onChange={(e) => setSiren(e.target.value.replace(/\D/g, '').slice(0, 9))}
                placeholder="123456789"
                className="h-9 w-48 rounded-md border border-slate-200 px-3 text-sm text-slate-700 tabular-nums focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
              />
            </label>
          </div>
        ) : mode === 'batch' ? (
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">SIREN a enrichir (un par ligne ou separes par virgule)</span>
            <textarea
              value={sirensInput}
              onChange={(e) => setSirensInput(e.target.value)}
              rows={4}
              placeholder={'123456789\n552081317'}
              className="w-full max-w-md rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 tabular-nums focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
            />
            <span className="text-xs text-slate-400">{parsedSirens.length} SIREN valides detectes</span>
          </div>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-700">Codes NAF (editeurs, separes par des virgules)</span>
              <input
                value={nafInput}
                onChange={(e) => setNafInput(e.target.value)}
                className="h-9 w-72 rounded-md border border-slate-200 px-3 text-sm text-slate-700 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-700">Limite societes</span>
              <input
                type="number"
                min={1}
                max={1000}
                value={limit}
                onChange={(e) => setLimit(Math.max(1, Math.min(1000, Number(e.target.value) || 1)))}
                className="h-9 w-28 rounded-md border border-slate-200 px-3 text-sm text-slate-700 tabular-nums focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
              />
            </label>
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            size="sm"
            icon={Play}
            disabled={!canLaunch || runMutation.isPending}
            onClick={() => runMutation.mutate()}
          >
            {runMutation.isPending ? 'Lancement…' : 'Lancer l’enrichissement'}
          </Button>
          <span className="text-xs text-slate-400">
            {mode === 'company'
              ? 'Enrichit les decideurs de cette societe.'
              : mode === 'batch'
                ? 'Enrichit les decideurs d’un lot de societes (par SIREN).'
                : 'Enrichit un lot de societes filtrees par code NAF.'}
          </span>
        </div>
      </div>

      {errorMsg && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ===== Jobs ===== */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 mb-3">Enrichissements</h2>
        <EnrichmentJobsTable jobs={jobsData?.items ?? []} />
      </div>
    </div>
  );
}
