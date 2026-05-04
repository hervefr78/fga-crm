// =============================================================================
// FGA CRM - Page detail Deal (v2 - refonte UI)
// Split-view + KPI strip + AI suggestions + timeline + stage stepper
// + Edition complete (DealEditModal) avec pricing one_shot / recurrent
// =============================================================================

import { useState, useMemo, useEffect, FormEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, ChevronRight, Mail, Phone, Linkedin, Building2,
  Edit2, Trash2, Copy, MoreHorizontal,
  Target, ListTodo, Activity as ActivityIcon, FileText,
  Send, Paperclip, Smile, Sparkles, Plus, Filter, Search,
  Video, Check, TrendingUp, User, Euro, Calendar,
  AlertTriangle, ArrowUpRight, Flame, AlertCircle, X,
} from 'lucide-react';
import clsx from 'clsx';

import {
  getDeal, getDeals, getActivities, getTasks,
  deleteDeal, updateDeal, getCompanies, getContacts, getDealNextAction,
} from '../api/client';
import type {
  Activity, Task, Deal, Company, Contact, PaginatedResponse,
  NextActionAction,
} from '../types';
import {
  DEAL_STAGES, DEAL_PRIORITIES, DEAL_PRICING_TYPES, PRICING_PERIOD_MONTHS,
} from '../types';
import { Button, ConfirmDialog, LoadingSpinner, Modal } from '../components/ui';
import AiCard from '../components/ai/AiCard';
import ComposerModal, { ComposerChannel } from '../components/activities/ComposerModal';

// -----------------------------------------------------------------------------
// Constantes
// -----------------------------------------------------------------------------

const SPLIT_VIEW_SIZE = 200;

const PIPELINE_STAGES = [
  { key: 'new', label: 'Nouveau' },
  { key: 'contacted', label: 'Contacte' },
  { key: 'meeting', label: 'Meeting' },
  { key: 'proposal', label: 'Proposition' },
  { key: 'negotiation', label: 'Negociation' },
  { key: 'won', label: 'Gagne' },
];

const STAGE_LABELS: Record<string, string> = Object.fromEntries(
  PIPELINE_STAGES.map((s) => [s.key, s.label]),
);
STAGE_LABELS.lost = 'Perdu';

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-blue-50 text-blue-700',
  high: 'bg-amber-50 text-amber-700',
  urgent: 'bg-red-50 text-red-600',
};
const PRIORITY_LABELS: Record<string, string> = {
  low: 'Basse', medium: 'Moyenne', high: 'Haute', urgent: 'Urgente',
};

const PRICING_LABELS: Record<string, string> = Object.fromEntries(
  DEAL_PRICING_TYPES.map((p) => [p.value, p.label]),
);

const PRICING_PERIOD_LABEL: Record<string, string> = {
  monthly: 'mensuel',
  quarterly: 'trimestriel',
  biannual: 'semestriel',
  annual: 'annuel',
};

const ACTIVITY_ICONS: Record<string, React.ElementType> = {
  email: Mail, call: Phone, meeting: Video, note: FileText,
  linkedin: Linkedin, task: Check,
};
const ACTIVITY_BG: Record<string, string> = {
  email: 'bg-blue-50 text-blue-600',
  call: 'bg-emerald-50 text-emerald-600',
  meeting: 'bg-indigo-50 text-indigo-600',
  note: 'bg-amber-50 text-amber-600',
  linkedin: 'bg-sky-50 text-sky-600',
  task: 'bg-slate-100 text-slate-600',
};

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

// -----------------------------------------------------------------------------
// Modal d'edition complete (pricing + cross-fields, repris de l'ancien
// DealDetail.tsx — DC8 : la logique reste localisee a la page mais factorisee
// dans un composant pour preserver la lisibilite)
// -----------------------------------------------------------------------------

interface EditForm {
  title: string;
  stage: string;
  amount: string;
  currency: string;
  probability: string;
  priority: string;
  expected_close_date: string;
  company_id: string;
  contact_id: string;
  description: string;
  pricing_type: string;
  recurring_amount: string;
  commitment_months: string;
  loss_reason: string;
}

function DealEditModal({
  open, onClose, deal, onSaved,
}: {
  open: boolean;
  onClose: () => void;
  deal: Deal;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<EditForm>(() => buildInitialForm(deal));
  const [error, setError] = useState<string | null>(null);

  // Re-init le form a chaque ouverture (le deal peut avoir change suite a une autre action)
  useEffect(() => {
    if (open) {
      setForm(buildInitialForm(deal));
      setError(null);
    }
  }, [open, deal]);

  const { data: companiesData } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 100 }],
    queryFn: () => getCompanies({ size: 100 }),
    enabled: open,
  });

  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', { size: 100 }],
    queryFn: () => getContacts({ size: 100 }),
    enabled: open,
  });

  const editMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateDeal(deal.id, data),
    onSuccess: () => onSaved(),
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Une erreur est survenue';
      setError(message);
    },
  });

  const companyOptions = (companiesData?.items ?? []).map((c) => ({ value: c.id, label: c.name }));
  const contactOptions = (contactsData?.items ?? []).map((c) => ({ value: c.id, label: c.full_name }));

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation cross-field (DC8 — meme regle que DealForm.tsx)
    if (form.pricing_type !== 'one_shot' && !form.recurring_amount.trim()) {
      setError('Le montant unitaire est obligatoire pour un abonnement.');
      return;
    }

    const data: Record<string, unknown> = {
      title: form.title.trim(),
      stage: form.stage,
      currency: form.currency,
      priority: form.priority,
      probability: parseInt(form.probability, 10) || 0,
      pricing_type: form.pricing_type,
    };
    if (form.expected_close_date) data.expected_close_date = form.expected_close_date;
    data.company_id = form.company_id || null;
    data.contact_id = form.contact_id || null;
    data.description = form.description.trim() || null;

    // loss_reason : conserve uniquement si stage='lost' (sinon on reset cote backend)
    if (form.stage === 'lost') {
      data.loss_reason = form.loss_reason.trim() || null;
    } else {
      data.loss_reason = null;
    }

    // Tarification
    if (form.pricing_type === 'one_shot') {
      data.recurring_amount = null;
      data.commitment_months = null;
      if (form.amount.trim()) data.amount = parseFloat(form.amount);
    } else {
      if (form.recurring_amount.trim()) {
        data.recurring_amount = parseFloat(form.recurring_amount);
      }
      if (form.commitment_months.trim()) {
        data.commitment_months = parseInt(form.commitment_months, 10);
      }
      // Recalcul du montant total = recurring * (commit / period_months)
      if (form.recurring_amount.trim() && form.commitment_months.trim()) {
        const months = PRICING_PERIOD_MONTHS[form.pricing_type] || 1;
        const totalPeriods = parseInt(form.commitment_months, 10) / months;
        data.amount = parseFloat(form.recurring_amount) * totalPeriods;
      }
    }

    editMutation.mutate(data);
  };

  return (
    <Modal open={open} onClose={onClose} title="Modifier le deal" size="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Titre + stage + priorite */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-3">
            <label className="block text-sm font-medium text-slate-700 mb-1">Titre</label>
            <input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Stage</label>
            <select
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {DEAL_STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Priorite</label>
            <select
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {DEAL_PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Probabilite (%)</label>
            <input
              type="number" min={0} max={100}
              value={form.probability}
              onChange={(e) => setForm({ ...form, probability: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Erreur */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-3 py-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Pricing type */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Type de tarification</label>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {DEAL_PRICING_TYPES.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setForm({ ...form, pricing_type: p.value })}
                className={clsx(
                  'px-3 py-2 text-xs font-medium rounded-lg border transition-colors',
                  form.pricing_type === p.value
                    ? 'bg-primary-50 border-primary-500 text-primary-700'
                    : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300',
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Montants conditionnels */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {form.pricing_type === 'one_shot' ? (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Montant</label>
              <input
                type="number" min={0} step={0.01}
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="0"
              />
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Montant {PRICING_PERIOD_LABEL[form.pricing_type] ?? ''}
                </label>
                <input
                  type="number" min={0} step={0.01}
                  value={form.recurring_amount}
                  onChange={(e) => setForm({ ...form, recurring_amount: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Engagement (mois)</label>
                <input
                  type="number" min={1} max={120}
                  value={form.commitment_months}
                  onChange={(e) => setForm({ ...form, commitment_months: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="12"
                />
              </div>
            </>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Devise</label>
            <input
              maxLength={3}
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 uppercase"
            />
          </div>
        </div>

        {/* Date + entreprise + contact */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Date de cloture prevue</label>
            <input
              type="date"
              value={form.expected_close_date}
              onChange={(e) => setForm({ ...form, expected_close_date: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Entreprise</label>
            <select
              value={form.company_id}
              onChange={(e) => setForm({ ...form, company_id: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Aucune</option>
              {companyOptions.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Contact</label>
            <select
              value={form.contact_id}
              onChange={(e) => setForm({ ...form, contact_id: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Aucun</option>
              {contactOptions.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[80px]"
            placeholder="Notes sur le deal..."
          />
        </div>

        {/* Loss reason — visible uniquement si stage='lost' */}
        {form.stage === 'lost' && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Raison de la perte</label>
            <textarea
              value={form.loss_reason}
              onChange={(e) => setForm({ ...form, loss_reason: e.target.value })}
              maxLength={255}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[60px]"
              placeholder="Ex : Budget non valide, choix d'un concurrent..."
            />
            <p className="text-xs text-slate-400 mt-1">{form.loss_reason.length}/255 caracteres</p>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose} icon={X}>Annuler</Button>
          <Button type="submit" loading={editMutation.isPending}>Enregistrer</Button>
        </div>
      </form>
    </Modal>
  );
}

function buildInitialForm(deal: Deal): EditForm {
  return {
    title: deal.title,
    stage: deal.stage,
    amount: deal.amount?.toString() ?? '',
    currency: deal.currency,
    probability: deal.probability?.toString() ?? '0',
    priority: deal.priority,
    expected_close_date: deal.expected_close_date ?? '',
    company_id: deal.company_id ?? '',
    contact_id: deal.contact_id ?? '',
    description: deal.description ?? '',
    pricing_type: deal.pricing_type,
    recurring_amount: deal.recurring_amount?.toString() ?? '',
    commitment_months: deal.commitment_months?.toString() ?? '',
    loss_reason: deal.loss_reason ?? '',
  };
}

// -----------------------------------------------------------------------------
// Sub-components UI (Kpi, Card, Tab, etc.)
// -----------------------------------------------------------------------------

function Kpi({ icon: Icon, label, value, suffix, trend }: {
  icon: React.ElementType; label: string; value: string; suffix?: string; trend?: string;
}) {
  return (
    <div className="bg-white px-4 py-3.5 flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 uppercase tracking-wider">
        <Icon className="w-3 h-3" />{label}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl font-semibold text-slate-900 tabular-nums tracking-tight">{value}</span>
        {suffix && <span className="text-xs text-slate-500 font-medium">{suffix}</span>}
      </div>
      {trend && (
        <div className="flex items-center gap-1 text-[11px] text-slate-500 font-medium">
          <ArrowUpRight className="w-3 h-3" />{trend}
        </div>
      )}
    </div>
  );
}

function Card({ title, icon: Icon, children }: {
  title: string; icon?: React.ElementType; children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          {Icon && <Icon className="w-3.5 h-3.5" />}{title}
        </div>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function Tab({ active, onClick, icon: Icon, label, count }: {
  active: boolean; onClick: () => void; icon: React.ElementType; label: string; count?: number;
}) {
  return (
    <button onClick={onClick} className={clsx(
      'inline-flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium rounded-t-md relative transition-colors',
      active ? 'text-slate-900' : 'text-slate-500 hover:text-slate-700',
    )}>
      <Icon className="w-3.5 h-3.5" />{label}
      {count != null && (
        <span className={clsx('text-xs px-1.5 py-0.5 rounded-full font-medium',
          active ? 'bg-primary-50 text-primary-700' : 'bg-slate-100 text-slate-500',
        )}>{count}</span>
      )}
      {active && <span className="absolute left-2 right-2 -bottom-px h-0.5 bg-slate-900 rounded-full" />}
    </button>
  );
}

function SideLink({ icon: Icon, label, value, href, internal }: {
  icon: React.ElementType; label: string; value?: string | null; href?: string | null; internal?: boolean;
}) {
  const content = (
    <>
      <div className="w-7 h-7 rounded-md bg-slate-50 flex items-center justify-center text-slate-500 flex-shrink-0">
        <Icon className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1 text-xs text-slate-500">{label}</div>
      <div className="text-sm font-medium text-slate-800 truncate max-w-[160px]">{value || <span className="text-slate-300">—</span>}</div>
    </>
  );
  if (href && value) {
    if (internal) {
      return <Link to={href} className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors text-primary-600">{content}</Link>;
    }
    return <a href={href} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors text-primary-600">{content}</a>;
  }
  return <div className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-50 last:border-0">{content}</div>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex items-center justify-between text-slate-500"><span>{label}</span>{children}</div>;
}

function ActivityFeed({
  activities,
  onChannelClick,
}: {
  activities: Activity[];
  onChannelClick: (c: ComposerChannel) => void;
}) {
  const grouped = useMemo(() => {
    const map = new Map<string, Activity[]>();
    for (const a of activities) {
      const day = formatDay(a.created_at);
      if (!map.has(day)) map.set(day, []);
      map.get(day)!.push(a);
    }
    return Array.from(map.entries());
  }, [activities]);

  const channels: { label: string; channel: ComposerChannel }[] = [
    { label: 'Note', channel: 'note' },
    { label: 'Email', channel: 'email' },
    { label: 'Appel', channel: 'call' },
    { label: 'RDV', channel: 'meeting' },
  ];

  return (
    <div>
      <div className="m-4 border border-slate-200 rounded-lg bg-slate-50/50">
        <div className="flex border-b border-slate-200 px-1.5">
          {channels.map(({ label, channel }) => (
            <button
              key={channel}
              type="button"
              onClick={() => onChannelClick(channel)}
              className="px-2.5 py-2 text-xs font-medium text-slate-500 border-b border-transparent hover:text-slate-700 -mb-px"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="px-3 py-2.5">
          <button
            type="button"
            onClick={() => onChannelClick('note')}
            className="w-full text-left text-sm text-slate-400 italic hover:text-slate-600 min-h-[40px]"
          >
            Cliquer ici pour ajouter une note rapide...
          </button>
        </div>
        <div className="flex items-center justify-between px-2 pb-2 pt-1 border-t border-slate-100">
          <div className="flex gap-0.5">
            <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100" aria-label="Pieces jointes"><Paperclip className="w-3.5 h-3.5" /></button>
            <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100" aria-label="Emoji"><Smile className="w-3.5 h-3.5" /></button>
            <button className="inline-flex items-center gap-1 px-2 py-1 rounded text-slate-500 hover:bg-slate-100 text-xs"><Sparkles className="w-3 h-3" />IA</button>
          </div>
          <div className="flex gap-1.5">
            <Button variant="primary" size="sm" icon={Send} onClick={() => onChannelClick('note')}>Publier</Button>
          </div>
        </div>
      </div>

      {activities.length === 0 ? (
        <EmptyTab icon={ActivityIcon} text="Aucune activite enregistree" />
      ) : (
        <div className="relative pb-4">
          <div className="absolute left-[31px] top-9 bottom-3 w-px bg-slate-100" />
          {grouped.map(([day, items]) => (
            <div key={day}>
              <div className="flex items-center gap-2 px-4 pt-3 pb-1.5">
                <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">{day}</span>
                <span className="flex-1 h-px bg-slate-100" />
              </div>
              {items.map((a) => {
                const Icon = ACTIVITY_ICONS[a.type] ?? FileText;
                return (
                  <div key={a.id} className="grid grid-cols-[28px_1fr_auto] gap-3 px-4 py-2.5 hover:bg-slate-50/60 transition-colors">
                    <div className={clsx('w-7 h-7 rounded-lg border flex items-center justify-center flex-shrink-0 relative z-10', ACTIVITY_BG[a.type] ?? 'bg-slate-100 text-slate-500', 'border-slate-200/60')}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="min-w-0 space-y-1">
                      <div className="text-sm font-medium text-slate-800">{a.subject || a.type}</div>
                      {a.content && (
                        <div className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2 leading-relaxed line-clamp-3">{a.content}</div>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 tabular-nums whitespace-nowrap">{formatTime(a.created_at)}</div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TasksList({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) return <EmptyTab icon={ListTodo} text="Aucune tache" />;
  return (
    <div>
      {tasks.map((t) => {
        // DC10 — Task expose `is_completed`
        const done = t.is_completed;
        return (
          <div key={t.id} className="grid grid-cols-[20px_1fr_auto] gap-3 items-center px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50/60 transition-colors">
            <div className={clsx('w-4 h-4 rounded border flex items-center justify-center', done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-300')}>
              {done && <Check className="w-3 h-3" />}
            </div>
            <div className={clsx('text-sm', done ? 'text-slate-400 line-through' : 'text-slate-800 font-medium')}>{t.title}</div>
            <div className="text-xs text-slate-400 tabular-nums">{t.due_date ? formatDate(t.due_date) : '—'}</div>
          </div>
        );
      })}
    </div>
  );
}

function EmptyTab({ icon: Icon, text }: { icon: React.ElementType; text: string }) {
  return (
    <div className="py-10 flex flex-col items-center justify-center text-center text-sm text-slate-400 gap-2">
      <div className="w-9 h-9 rounded-lg bg-slate-50 flex items-center justify-center"><Icon className="w-4 h-4" /></div>
      {text}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

function formatDate(d?: string | null) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
}
function formatTime(d?: string | null) {
  if (!d) return '';
  return new Date(d).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}
function formatDay(d?: string | null) {
  if (!d) return '';
  const date = new Date(d);
  const today = new Date();
  const yesterday = new Date(); yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Aujourd'hui";
  if (date.toDateString() === yesterday.toDateString()) return 'Hier';
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
}
