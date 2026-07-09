// =============================================================================
// FGA CRM - Page Lead Engine : queue priorisee + Signal Inbox (V1 complete)
// =============================================================================
// Vues (docs/LEAD_ENGINE_VISION.md §3) :
//  - File d'attente : leads mmf_gap tries gap x fraicheur des fonds, avec
//    [Drafter] -> outreach-v1 -> relecture -> composer (envoi valide par l'humain).
//  - Signal Inbox : flux chronologique, actions 1-clic par type (P1/P2/P3).
// La page = hooks + assemblage ; panneaux dans components/leadEngine/.
// =============================================================================

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Banknote, Check, Crosshair, Inbox, Loader2, RadioTower, ShieldAlert, X,
} from 'lucide-react';

import { qualifyContact } from '../api/client';
import {
  draftLeadSignal, getLeadFunnel, getLeadQueue, listLeadSignals, runLeadScan,
  updateLeadSignal,
} from '../api/leadEngine';
import KpiCard from '../components/dashboard/KpiCard';
import { useCompanyBulkAction } from '../components/companies/useCompanyBulkAction';
import ComposeModal, { type ComposePrefill } from '../components/email/ComposeModal';
import DraftModal from '../components/leadEngine/DraftModal';
import FunnelStrip from '../components/leadEngine/FunnelStrip';
import LeadQueuePanel from '../components/leadEngine/LeadQueuePanel';
import SignalRow from '../components/leadEngine/SignalRow';
import { Button, EmptyState, LoadingSpinner, Pagination, Tabs } from '../components/ui';
import { useAuth } from '../contexts/useAuth';
import { isManagerOrAbove } from '../types';
import type {
  LeadSignal, LeadSignalDraft, LeadSignalStatus, LeadSignalType,
  LeadSignalUpdateInput,
} from '../types/leadEngine';

const PAGE_SIZE = 20;

const VIEW_TABS = [
  { key: 'queue', label: "File d'attente" },
  { key: 'inbox', label: 'Signal Inbox' },
];

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

  const [view, setView] = useState<'queue' | 'inbox'>('queue');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('new');
  const [typeFilter, setTypeFilter] = useState<LeadSignalType | 'all'>('all');
  const [page, setPage] = useState(1);
  const [scanMsg, setScanMsg] = useState<string | null>(null);

  // Draft en relecture + composer pre-rempli (envoi valide par l'humain)
  const [draftView, setDraftView] = useState<{ signalId: string; draft: LeadSignalDraft } | null>(null);
  const [compose, setCompose] = useState<{ signalId: string; prefill: ComposePrefill } | null>(null);

  // Action longue (audit / recherche decideurs) : une seule a la fois.
  const bulk = useCompanyBulkAction();
  const [busySignalId, setBusySignalId] = useState<string | null>(null);

  const invalidateAll = () => {
    void queryClient.invalidateQueries({ queryKey: ['lead-signals'] });
    void queryClient.invalidateQueries({ queryKey: ['lead-queue'] });
    void queryClient.invalidateQueries({ queryKey: ['lead-funnel'] });
  };

  // ---- Queries ----
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
  const { data: queue, isLoading: queueLoading } = useQuery({
    queryKey: ['lead-queue'],
    queryFn: () => getLeadQueue(50),
    enabled: hasAccess,
  });
  const { data: funnel } = useQuery({
    queryKey: ['lead-funnel'],
    queryFn: () => getLeadFunnel(30),
    enabled: hasAccess,
  });

  // ---- Mutations ----
  const patchSignal = useMutation({
    mutationFn: ({ id, input }: { id: string; input: LeadSignalUpdateInput }) =>
      updateLeadSignal(id, input),
    onSettled: invalidateAll,
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
      invalidateAll();
    },
    onError: () => setScanMsg('Scan impossible (module désactivé ?)'),
  });

  const draft = useMutation({
    mutationFn: (signal: LeadSignal) => draftLeadSignal(signal.id),
    onSuccess: (res) => {
      setDraftView({
        signalId: res.signal_id,
        draft: {
          contact_id: res.contact_id, contact_name: res.contact_name,
          contact_email: res.contact_email, subject: res.subject, body: res.body,
          angle_rationale: res.angle_rationale, generated_at: res.generated_at,
          prompt_version: res.meta.prompt_version,
        },
      });
      invalidateAll();
    },
    onError: (err) => {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setScanMsg(detail ?? 'Draft impossible');
    },
  });

  const qualify = useMutation({
    mutationFn: (contactId: string) => qualifyContact(contactId),
    onSettled: invalidateAll,
  });

  // ---- Actions ----
  const launchBulk = (signal: LeadSignal, kind: 'audit' | 'contacts') => {
    if (!signal.company_id || bulk.isRunning) return;
    const company = {
      id: signal.company_id,
      name: signal.payload_json.company_name ?? '',
      startup_radar_id: signal.payload_json.startup_radar_id ?? null,
    };
    if (kind === 'audit') bulk.startAudit([company]);
    else bulk.startContacts([company]);
    setBusySignalId(signal.id);
    patchSignal.mutate({ id: signal.id, input: { status: 'actioned', action_kind: kind } });
  };

  const handleInboxAction = (signal: LeadSignal) => {
    if (signal.signal_type === 'funding_detected') return launchBulk(signal, 'audit');
    if (signal.signal_type === 'mmf_gap') return launchBulk(signal, 'contacts');
    // inbound_new (P3) : qualification SPICED puis trace
    const contactId = signal.payload_json.contact_id;
    if (!contactId || qualify.isPending) return;
    setBusySignalId(signal.id);
    qualify.mutate(contactId, {
      onSuccess: () => patchSignal.mutate({
        id: signal.id, input: { status: 'actioned', action_kind: 'qualify' },
      }),
      onSettled: () => setBusySignalId(null),
    });
  };

  const handleDraft = (signal: LeadSignal) => {
    const existing = signal.payload_json.draft;
    if (existing) return setDraftView({ signalId: signal.id, draft: existing });
    if (draft.isPending) return;
    setBusySignalId(signal.id);
    draft.mutate(signal, { onSettled: () => setBusySignalId(null) });
  };

  const handleCompose = () => {
    if (!draftView) return;
    setCompose({
      signalId: draftView.signalId,
      prefill: {
        contactId: draftView.draft.contact_id,
        toEmail: draftView.draft.contact_email,
        subject: draftView.draft.subject,
        body: draftView.draft.body,
      },
    });
    setDraftView(null);
  };

  const handleSent = () => {
    if (!compose) return;
    // Trace l'envoi sur le signal (funnel `sent`) — self-loop actioned autorise.
    patchSignal.mutate({
      id: compose.signalId,
      input: { status: 'actioned', action_kind: 'outreach' },
    });
    setCompose(null);
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
            Le MMF gap déclenche l'outreach, la levée déclenche un audit.
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

      {/* Funnel par play */}
      {funnel && <FunnelStrip funnel={funnel} />}

      {/* Progression de l'action longue en cours */}
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

      {/* Vue : queue | inbox */}
      <Tabs tabs={VIEW_TABS} activeTab={view} onChange={(key) => setView(key as 'queue' | 'inbox')} />

      {view === 'queue' ? (
        <LeadQueuePanel
          items={queue?.items ?? []}
          isLoading={queueLoading}
          busySignalId={busySignalId}
          onDraft={handleDraft}
          onEnrich={(s) => launchBulk(s, 'contacts')}
          onDismiss={(s) => patchSignal.mutate({ id: s.id, input: { status: 'ignored' } })}
        />
      ) : (
        <>
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
              <option value="inbound_new">Inbound</option>
            </select>
          </div>

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
                    busy={busySignalId === signal.id && (bulk.isRunning || qualify.isPending)}
                    onAction={handleInboxAction}
                    onIgnore={(s) => patchSignal.mutate({ id: s.id, input: { status: 'ignored' } })}
                    onReopen={(s) => patchSignal.mutate({ id: s.id, input: { status: 'new' } })}
                  />
                ))}
              </ul>
            )}
          </div>

          <Pagination page={page} pages={pages} total={data?.total ?? 0} onPageChange={setPage} />
        </>
      )}

      {/* Relecture du draft puis composer (envoi valide par l'humain) */}
      <DraftModal
        open={draftView !== null}
        draft={draftView?.draft ?? null}
        onClose={() => setDraftView(null)}
        onCompose={handleCompose}
      />
      <ComposeModal
        open={compose !== null}
        onClose={() => setCompose(null)}
        prefill={compose?.prefill}
        onSent={handleSent}
      />
    </div>
  );
}
