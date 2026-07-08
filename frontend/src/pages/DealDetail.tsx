// =============================================================================
// FGA CRM - Page detail Deal (v2 - refonte UI)
// Split-view + KPI strip + AI suggestions + timeline + stage stepper
// + Edition complete (DealEditModal) avec pricing one_shot / recurrent
//
// Sous-composants extraits dans components/deal/ (refactor C5) :
//   - dealUtils.ts        : constantes + helpers de format
//   - DealAtoms.tsx       : Kpi, Card, Tab, SideLink, Row, EmptyTab
//   - DealActivityFeed.tsx: feed d'activite (composer + timeline)
//   - DealTasksList.tsx   : liste des taches
//   - DealEditModal.tsx   : modale d'edition complete (pricing)
// =============================================================================

import { useState, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, ChevronRight, Building2,
  Edit2, Trash2, Copy, MoreHorizontal,
  Target, ListTodo, Activity as ActivityIcon, FileText,
  Plus, Filter, Search,
  TrendingUp, User, Euro, Calendar,
  AlertTriangle, Flame,
} from 'lucide-react';
import clsx from 'clsx';

import {
  getDeal, getDeals, getActivities, getTasks,
  deleteDeal, getDealNextAction,
} from '../api/client';
import type {
  Activity, Task, Deal, NextActionAction,
} from '../types';
import { PRICING_PERIOD_MONTHS } from '../types';
import { Button, ConfirmDialog, LoadingSpinner } from '../components/ui';
import AiCard from '../components/ai/AiCard';
import DealScoreCard from '../components/pipeline/DealScoreCard';
import ComposerModal, { ComposerChannel } from '../components/activities/ComposerModal';
import {
  SPLIT_VIEW_SIZE, PIPELINE_STAGES, STAGE_LABELS,
  PRIORITY_COLORS, PRIORITY_LABELS, PRICING_LABELS, formatDate,
} from '../components/deal/dealUtils';
import { Kpi, Card, Tab, SideLink, Row } from '../components/deal/DealAtoms';
import ActivityFeed from '../components/deal/DealActivityFeed';
import TasksList from '../components/deal/DealTasksList';
import DealEditModal from '../components/deal/DealEditModal';

// -----------------------------------------------------------------------------
// Page
// -----------------------------------------------------------------------------

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [listSearch, setListSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'activity' | 'tasks'>('activity');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerChannel, setComposerChannel] = useState<ComposerChannel>('note');

  const { data: dealsList } = useQuery({
    queryKey: ['deals', { search: listSearch, size: SPLIT_VIEW_SIZE }],
    queryFn: () => getDeals({ search: listSearch, size: SPLIT_VIEW_SIZE }),
  });

  const { data: deal, isLoading } = useQuery({
    queryKey: ['deal', id],
    queryFn: () => getDeal(id!),
    enabled: !!id,
  });

  const { data: activitiesData } = useQuery({
    queryKey: ['activities', { deal_id: id }],
    queryFn: () => getActivities({ deal_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: tasksData } = useQuery({
    queryKey: ['tasks', { deal_id: id }],
    queryFn: () => getTasks({ deal_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: nextAction, isLoading: nextActionLoading } = useQuery({
    queryKey: ['next-action', 'deal', id],
    queryFn: () => getDealNextAction(id!),
    enabled: !!id,
    retry: false,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteDeal(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['deals'] });
      navigate('/pipeline');
    },
  });

  const dealsListItems: Deal[] = useMemo(() => dealsList?.items ?? [], [dealsList]);
  const activities: Activity[] = useMemo(() => activitiesData?.items ?? [], [activitiesData]);
  const tasks: Task[] = useMemo(() => tasksData?.items ?? [], [tasksData]);

  const kpi = useMemo(() => {
    if (!deal) return { weighted: 0, daysToClose: 0, ageDays: 0, openTasks: 0 };
    const weighted = ((deal.amount ?? 0) * (deal.probability ?? 0)) / 100;
    const daysToClose = deal.expected_close_date
      ? Math.ceil((new Date(deal.expected_close_date).getTime() - Date.now()) / 86400000)
      : 0;
    const ageDays = deal.created_at
      ? Math.floor((Date.now() - new Date(deal.created_at).getTime()) / 86400000)
      : 0;
    const openTasks = tasks.filter((t) => !t.is_completed).length;
    return { weighted, daysToClose, ageDays, openTasks };
  }, [deal, tasks]);

  if (isLoading || !deal) {
    return <div className="flex items-center justify-center h-full"><LoadingSpinner /></div>;
  }

  const isWon = deal.stage === 'won';
  const isLost = deal.stage === 'lost';
  const stageIdx = PIPELINE_STAGES.findIndex((s) => s.key === deal.stage);

  const handleAiAction = (action: NextActionAction) => {
    if (action.type === 'create_task') {
      // Pour ce sprint : on log une note. Une vraie modale tache pourra etre
      // branchee plus tard (DC17 — fragilite signalee).
      setComposerChannel('note');
      setComposerOpen(true);
    } else if (action.type === 'compose_email') {
      setComposerChannel('email');
      setComposerOpen(true);
    }
  };

  return (
    <div className="flex h-full bg-slate-50">

      {/* ===== LISTE ===== */}
      <aside className="w-[340px] border-r border-slate-200 bg-white flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-slate-100 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <h2 className="text-lg font-semibold text-slate-900">Pipeline</h2>
              <span className="text-xs text-slate-400 tabular-nums">{dealsListItems.length}</span>
            </div>
            <div className="flex gap-1">
              <button className="p-1.5 rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                <Filter className="w-4 h-4" />
              </button>
              <Link to="/pipeline" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-primary-600 text-white text-xs font-medium hover:bg-primary-700">
                <Plus className="w-3.5 h-3.5" /> Nouveau
              </Link>
            </div>
          </div>
          <div className="flex items-center gap-2 px-2.5 h-8 bg-slate-50 border border-slate-100 rounded-md">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input value={listSearch} onChange={(e) => setListSearch(e.target.value)} placeholder="Rechercher..." className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {dealsListItems.map((d) => (
            <Link
              key={d.id}
              to={`/pipeline/${d.id}`}
              className={clsx(
                'block p-2.5 rounded-lg transition-colors mb-0.5',
                d.id === id ? 'bg-slate-50 shadow-sm' : 'hover:bg-slate-50'
              )}
            >
              <div className="text-sm font-medium text-slate-800 truncate">{d.title}</div>
              <div className="flex items-center justify-between mt-1 text-xs text-slate-400">
                <span className="truncate">{STAGE_LABELS[d.stage] ?? d.stage}</span>
                <span className="tabular-nums font-medium text-slate-600">{((d.amount ?? 0) / 1000).toFixed(1)}k</span>
              </div>
            </Link>
          ))}
        </div>
      </aside>

      {/* ===== DETAIL ===== */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="flex items-center gap-2 px-6 h-11 border-b border-slate-200 bg-white">
          <Link to="/pipeline" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded">
            <ArrowLeft className="w-3.5 h-3.5" /> Pipeline
          </Link>
          {deal.company_name && deal.company_id && (
            <>
              <ChevronRight className="w-3 h-3 text-slate-300" />
              <Link to={`/companies/${deal.company_id}`} className="text-xs text-slate-500 hover:text-slate-700">
                {deal.company_name}
              </Link>
            </>
          )}
          <div className="flex-1" />
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"><Copy className="w-3.5 h-3.5" /></button>
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"><MoreHorizontal className="w-3.5 h-3.5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-[1100px] mx-auto px-7 py-5 pb-16">

            {/* HEADER */}
            <div className="space-y-5 pb-6 border-b border-slate-200">
              <div className="flex items-start gap-4">
                <div className={clsx(
                  'w-14 h-14 rounded-2xl border flex items-center justify-center',
                  isWon ? 'bg-emerald-50 border-emerald-200 text-emerald-600' :
                  isLost ? 'bg-red-50 border-red-200 text-red-500' :
                  'bg-gradient-to-br from-amber-50 to-orange-100 border-amber-200/50 text-amber-700'
                )}>
                  <Target className="w-6 h-6" />
                </div>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="text-[11px] uppercase tracking-wider font-medium text-slate-400">
                    Opportunite · {PRIORITY_LABELS[deal.priority]} · {deal.currency}
                  </div>
                  <h1 className="text-2xl font-semibold text-slate-900 tracking-tight flex items-center gap-3 flex-wrap">
                    {deal.title}
                    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', PRIORITY_COLORS[deal.priority])}>
                      {deal.priority === 'urgent' && <Flame className="w-3 h-3 mr-1" />}
                      {PRIORITY_LABELS[deal.priority]}
                    </span>
                  </h1>
                  <div className="flex items-center gap-2 flex-wrap text-sm text-slate-500">
                    {deal.company_name && deal.company_id && (
                      <Link to={`/companies/${deal.company_id}`} className="inline-flex items-center gap-1 hover:text-primary-600">
                        <Building2 className="w-3 h-3" />{deal.company_name}
                      </Link>
                    )}
                    {deal.contact_name && deal.contact_id && (
                      <>
                        <span className="text-slate-300">·</span>
                        <Link to={`/contacts/${deal.contact_id}`} className="inline-flex items-center gap-1 hover:text-primary-600">
                          <User className="w-3 h-3" />{deal.contact_name}
                        </Link>
                      </>
                    )}
                    {deal.expected_close_date && (
                      <>
                        <span className="text-slate-300">·</span>
                        <span className="inline-flex items-center gap-1">
                          <Calendar className="w-3 h-3" />Cloture {formatDate(deal.expected_close_date)}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <Button variant="secondary" size="sm" icon={Edit2} onClick={() => setEditOpen(true)}>Modifier</Button>
                  <button onClick={() => setDeleteOpen(true)} className="p-1.5 rounded text-slate-400 hover:bg-red-50 hover:text-red-600">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Stage stepper */}
              {!isLost ? (
                <div className="grid grid-cols-6 gap-1">
                  {PIPELINE_STAGES.map((s, i) => {
                    const active = i <= stageIdx;
                    const current = i === stageIdx;
                    return (
                      <div key={s.key} className="flex flex-col gap-1.5">
                        <div className={clsx(
                          'h-1.5 rounded-full',
                          active ? (current ? 'bg-primary-600' : 'bg-primary-300') : 'bg-slate-200'
                        )} />
                        <div className={clsx(
                          'text-[11px] font-medium',
                          current ? 'text-slate-900' : active ? 'text-slate-600' : 'text-slate-400'
                        )}>
                          {s.label}
                          {current && <span className="ml-1">·</span>}
                          {current && <span className="ml-0.5 text-primary-600">{deal.probability ?? 0}%</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-50 border border-red-200/60">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <span className="text-sm font-medium text-red-700">Deal perdu</span>
                  {deal.loss_reason && (
                    <>
                      <span className="text-red-300">·</span>
                      <span className="text-sm text-red-600">{deal.loss_reason}</span>
                    </>
                  )}
                </div>
              )}

              {/* KPI strip */}
              <div className="grid grid-cols-4 gap-px bg-slate-200 rounded-xl overflow-hidden border border-slate-200">
                <Kpi
                  icon={Euro}
                  label="Montant"
                  value={`${((deal.amount ?? 0) / 1000).toFixed(1)}`}
                  suffix={`k ${deal.currency}`}
                  trend={PRICING_LABELS[deal.pricing_type] ?? deal.pricing_type}
                />
                <Kpi
                  icon={TrendingUp}
                  label="Pondere"
                  value={`${(kpi.weighted / 1000).toFixed(1)}`}
                  suffix="k"
                  trend={`${deal.probability ?? 0}% de chances`}
                />
                <Kpi
                  icon={Calendar}
                  label="Delai"
                  value={kpi.daysToClose >= 0 ? String(kpi.daysToClose) : `+${Math.abs(kpi.daysToClose)}`}
                  suffix={kpi.daysToClose >= 0 ? 'jours' : 'j retard'}
                  trend={deal.expected_close_date ? formatDate(deal.expected_close_date) : '—'}
                />
                <Kpi
                  icon={ActivityIcon}
                  label="Anciennete"
                  value={String(kpi.ageDays)}
                  suffix="jours"
                  trend={`${activities.length} activites`}
                />
              </div>
            </div>

            {/* GRID */}
            <div className="grid grid-cols-[1fr_320px] gap-6 pt-5">
              <div className="min-w-0 flex flex-col gap-4">

                <AiCard data={nextAction} loading={nextActionLoading} onAction={handleAiAction} />

                {/* Score IA (workflow scoring — fit + intent + opportunite message) */}
                <DealScoreCard deal={deal} />

                {deal.description && (
                  <Card title="Contexte" icon={FileText}>
                    <p className="text-sm text-slate-700 leading-relaxed text-pretty whitespace-pre-line">{deal.description}</p>
                  </Card>
                )}

                <div className="flex items-center gap-0.5 border-b border-slate-200 px-1 mt-2">
                  <Tab active={activeTab === 'activity'} onClick={() => setActiveTab('activity')} icon={ActivityIcon} label="Activite" count={activities.length} />
                  <Tab active={activeTab === 'tasks'} onClick={() => setActiveTab('tasks')} icon={ListTodo} label="Taches" count={tasks.length} />
                  <div className="flex-1" />
                  {activeTab === 'activity' && (
                    <Button variant="secondary" size="sm" icon={Plus} className="mb-1" onClick={() => { setComposerChannel('note'); setComposerOpen(true); }}>
                      Ajouter
                    </Button>
                  )}
                </div>

                <div className="bg-white border border-slate-200 border-t-0 rounded-b-xl rounded-t-none -mt-4 overflow-hidden">
                  {activeTab === 'activity' && (
                    <ActivityFeed
                      activities={activities}
                      onChannelClick={(c) => { setComposerChannel(c); setComposerOpen(true); }}
                    />
                  )}
                  {activeTab === 'tasks' && <TasksList tasks={tasks} />}
                </div>
              </div>

              {/* SIDE */}
              <div className="flex flex-col gap-4">
                <Card title="Tarification">
                  <div className="space-y-2.5 text-xs">
                    <Row label="Type"><span className="text-slate-700 font-medium">{PRICING_LABELS[deal.pricing_type] ?? deal.pricing_type}</span></Row>
                    {deal.recurring_amount != null && (
                      <Row label="Recurrent"><span className="text-slate-700 font-medium tabular-nums">{deal.recurring_amount.toLocaleString('fr-FR')} {deal.currency}</span></Row>
                    )}
                    {deal.commitment_months != null && (
                      <Row label="Engagement"><span className="text-slate-700 font-medium">{deal.commitment_months} mois</span></Row>
                    )}
                    {/* MRR calcule */}
                    {deal.pricing_type !== 'one_shot' && deal.recurring_amount != null && PRICING_PERIOD_MONTHS[deal.pricing_type] && (
                      <Row label="MRR">
                        <span className="text-slate-700 font-medium tabular-nums">
                          {(deal.recurring_amount / PRICING_PERIOD_MONTHS[deal.pricing_type]).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} {deal.currency}
                        </span>
                      </Row>
                    )}
                    <Row label="Probabilite">
                      <div className="flex items-center gap-1.5">
                        <div className="w-12 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-primary-500" style={{ width: `${deal.probability ?? 0}%` }} />
                        </div>
                        <span className="text-slate-700 font-medium tabular-nums">{deal.probability ?? 0}%</span>
                      </div>
                    </Row>
                  </div>
                </Card>

                <Card title="Liens">
                  <div className="-mx-4 -my-4">
                    <SideLink icon={Building2} label="Entreprise" value={deal.company_name} href={deal.company_id ? `/companies/${deal.company_id}` : null} internal />
                    <SideLink icon={User} label="Contact" value={deal.contact_name} href={deal.contact_id ? `/contacts/${deal.contact_id}` : null} internal />
                  </div>
                </Card>

                <Card title="Meta">
                  <div className="space-y-2 text-xs">
                    <Row label="Cree"><span className="text-slate-700">{formatDate(deal.created_at)}</span></Row>
                    {deal.actual_close_date && (
                      <Row label="Cloture le"><span className="text-slate-700 font-medium">{formatDate(deal.actual_close_date)}</span></Row>
                    )}
                    {deal.owner_name && <Row label="Owner"><span className="text-slate-700">{deal.owner_name}</span></Row>}
                  </div>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
        title="Supprimer ce deal ?"
        message={`Voulez-vous vraiment supprimer « ${deal.title} » ? Cette action est irreversible.`}
        confirmLabel="Supprimer"
        loading={deleteMutation.isPending}
      />

      <DealEditModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        deal={deal}
        onSaved={() => {
          setEditOpen(false);
          void queryClient.invalidateQueries({ queryKey: ['deal', id] });
          void queryClient.invalidateQueries({ queryKey: ['deals'] });
        }}
      />

      <ComposerModal
        open={composerOpen}
        onClose={() => setComposerOpen(false)}
        initialChannel={composerChannel}
        dealId={id}
      />
    </div>
  );
}
