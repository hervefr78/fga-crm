// =============================================================================
// FGA CRM - Page Lead Engine : Signal Inbox (Slice V1.1)
// =============================================================================
// Flux des signaux detectes (docs/LEAD_ENGINE_VISION.md §3.2) + actions 1-clic :
//  - funding_detected (P2) -> lance l'audit SR du message (jamais d'outreach) ;
//  - mmf_gap (P1)          -> lance la recherche de decideurs (prepare l'outreach).
// L'orchestration audit/enrichissement reutilise useCompanyBulkAction (poll +
// import), sur une liste d'une seule societe. La page = hooks + assemblage.
// =============================================================================

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Banknote, Check, Crosshair, Inbox, Loader2, RadioTower, ShieldAlert, X,
} from 'lucide-react';

import { runLeadScan, listLeadSignals, updateLeadSignal } from '../api/leadEngine';
import KpiCard from '../components/dashboard/KpiCard';
import { useCompanyBulkAction } from '../components/companies/useCompanyBulkAction';
import SignalRow from '../components/leadEngine/SignalRow';
import { Button, EmptyState, LoadingSpinner, Pagination, Tabs } from '../components/ui';
import { useAuth } from '../contexts/useAuth';
import { isManagerOrAbove } from '../types';
import type {
  LeadSignal, LeadSignalStatus, LeadSignalType, LeadSignalUpdateInput,
} from '../types/leadEngine';

const PAGE_SIZE = 20;

const STATUS_TABS = [
  { key: 'new', label: 'Nouveaux' },
  { key: 'actioned', label: 'Traités' },
  { key: 'ignored', label: 'Ignorés' },
  { key: 'all', label: 'Tous' },
];

type StatusFilter = LeadSignalStatus | 'all';

export default function LeadEnginePage() {
  const { user } = useAuth();
  const hasAccess = isManagerOrAbove(user);
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('new');
  const [typeFilter, setTypeFilter] = useState<LeadSignalType | 'all'>('all');
  const [page, setPage] = useState(1);
  const [scanMsg, setScanMsg] = useState<string | null>(null);

  // Action en cours (audit / recherche decideurs) : une seule a la fois.
  const bulk = useCompanyBulkAction();
  const [busySignalId, setBusySignalId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['lead-signals', statusFilter, typeFilter, page],
    queryFn: () => listLeadSignals({
      status: statusFilter === 'all' ? undefined : statusFilter,
      signal_type: typeFilter === 'all' ? undefined : typeFilter,
      page,
      size: PAGE_SIZE,
    }),
    enabled: hasAccess,
  });

  const patchSignal = useMutation({
    mutationFn: ({ id, input }: { id: string; input: LeadSignalUpdateInput }) =>
      updateLeadSignal(id, input),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['lead-signals'] }),
  });

  const scan = useMutation({
    mutationFn: runLeadScan,
    onSuccess: (res) => {
      const n = Object.values(res.created).reduce((a, b) => a + b, 0);
      setScanMsg(
        n === 0 ? 'Aucun nouveau signal'
          : n === 1 ? '1 nouveau signal'
            : `${n} nouveaux signaux`,
      );
      void queryClient.invalidateQueries({ queryKey: ['lead-signals'] });
    },
    onError: () => setScanMsg('Scan impossible (module désactivé ?)'),
  });

  // Action 1-clic : lance la brique existante puis trace la transition.
  const handleAction = (signal: LeadSignal) => {
    if (!signal.company_id || bulk.isRunning) return;
    const company = {
      id: signal.company_id,
      name: signal.payload_json.company_name ?? '',
      startup_radar_id: signal.payload_json.startup_radar_id ?? null,
    };
    const isFunding = signal.signal_type === 'funding_detected';
    if (isFunding) bulk.startAudit([company]);
    else bulk.startContacts([company]);
    setBusySignalId(signal.id);
    patchSignal.mutate({
      id: signal.id,
      input: { status: 'actioned', action_kind: isFunding ? 'audit' : 'contacts' },
    });
  };

  if (!hasAccess) {
    return (
      <div className="px-8 py-7">
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-red-50 flex items-center justify-center">
            <ShieldAlert className="w-6 h-6 text-red-500" />
          </div>
          <h1 className="text-lg font-semibold text-slate-800">Accès non autorisé</h1>
          <p className="text-sm text-slate-500 max-w-sm">
            Le module Lead Engine est réservé aux administrateurs et managers.
          </p>
        </div>
      </div>
    );
  }

  const stats = data?.stats;
  const items = data?.items ?? [];
  const pages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;
  const bulkTask = bulk.tasks[0];

  return (
    <div className="px-8 py-7 space-y-6">
      {/* En-tete */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Lead Engine</h1>
          <p className="text-sm text-slate-500 mt-1">
            Signal Inbox — le MMF gap déclenche l'outreach, la levée déclenche un audit.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {scanMsg && <span className="text-sm text-slate-500">{scanMsg}</span>}
          <Button
            icon={RadioTower}
            loading={scan.isPending}
            onClick={() => { setScanMsg(null); scan.mutate(); }}
          >
            Scanner maintenant
          </Button>
        </div>
      </div>

      {/* KPI */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard title="Signaux à traiter" value={String(stats.new_total)}
            icon={Inbox} color="text-primary-600" bgColor="bg-primary-50" />
          <KpiCard title="MMF gaps" value={String(stats.new_mmf)}
            subtitle="déclencheurs d'outreach"
            icon={Crosshair} color="text-primary-600" bgColor="bg-primary-50" />
          <KpiCard title="Levées à auditer" value={String(stats.new_funding)}
            subtitle="qualificateur, pas déclencheur"
            icon={Banknote} color="text-amber-600" bgColor="bg-amber-50" />
          <KpiCard title="Traités (7 j)" value={String(stats.actioned_7d)}
            icon={Check} color="text-emerald-600" bgColor="bg-emerald-50" />
        </div>
      )}

      {/* Progression de l'action en cours (audit ~minutes : on peut quitter la page) */}
      {bulk.action && bulkTask && (
        <div className="rounded-xl border border-primary-100 bg-primary-50/40 px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-slate-700">
            {bulk.isRunning
              ? <Loader2 className="w-4 h-4 text-primary-600 animate-spin shrink-0" />
              : bulkTask.status === 'done'
                ? <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                : <X className="w-4 h-4 text-red-500 shrink-0" />}
            <span>
              {bulk.action === 'audit' ? 'Audit du message' : 'Recherche de décideurs'}
              {' — '}{bulkTask.name} :{' '}
              {bulk.isRunning ? 'en cours…' : bulkTask.status === 'done' ? 'terminé' : 'échec'}
            </span>
          </div>
          {!bulk.isRunning && (
            <Button size="sm" variant="ghost" onClick={() => { bulk.reset(); setBusySignalId(null); }}>
              Fermer
            </Button>
          )}
        </div>
      )}

      {/* Filtres */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          tabs={STATUS_TABS}
          activeTab={statusFilter}
          onChange={(key) => { setStatusFilter(key as StatusFilter); setPage(1); }}
        />
        <select
          value={typeFilter}
          aria-label="Filtrer par type de signal"
          onChange={(e) => { setTypeFilter(e.target.value as LeadSignalType | 'all'); setPage(1); }}
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700 bg-white"
        >
          <option value="all">Tous les types</option>
          <option value="mmf_gap">MMF gap</option>
          <option value="funding_detected">Levée détectée</option>
        </select>
      </div>

      {/* Inbox */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
        {isLoading ? (
          <div className="p-12 flex justify-center"><LoadingSpinner /></div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Inbox}
            message="Aucun signal — le scan tourne toutes les heures, ou lancez « Scanner maintenant »."
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((signal) => (
              <SignalRow
                key={signal.id}
                signal={signal}
                busy={bulk.isRunning && busySignalId === signal.id}
                onAction={handleAction}
                onIgnore={(s) => patchSignal.mutate({ id: s.id, input: { status: 'ignored' } })}
                onReopen={(s) => patchSignal.mutate({ id: s.id, input: { status: 'new' } })}
              />
            ))}
          </ul>
        )}
      </div>

      <Pagination page={page} pages={pages} total={data?.total ?? 0} onPageChange={setPage} />
    </div>
  );
}
