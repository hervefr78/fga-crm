// =============================================================================
// FGA CRM - Page detail Contact (v2 - refonte UI)
// Split-view + KPI strip + AI suggestions + timeline activite
// =============================================================================

import { useState, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, ChevronRight, Mail, Phone, Linkedin, Building2,
  Edit2, Trash2, Copy, ExternalLink, MoreHorizontal,
  Target, ListTodo, Activity as ActivityIcon, FileText,
  Send, Paperclip, Smile, Sparkles, Star, Plus, Filter, Search,
  Video, Check, TrendingUp, Briefcase, ArrowUpRight,
} from 'lucide-react';
import clsx from 'clsx';

import {
  getContact, getContacts, getActivities, getDeals, getTasks,
  deleteContact, getContactNextAction,
} from '../api/client';
import type { Contact, Activity, Deal, Task, NextActionAction } from '../types';
import { Button, ConfirmDialog, LoadingSpinner, Modal } from '../components/ui';
import ContactForm from '../components/contacts/ContactForm';
import ComposeModal from '../components/email/ComposeModal';
import AiCard from '../components/ai/AiCard';
import ComposerModal, { ComposerChannel } from '../components/activities/ComposerModal';

// -----------------------------------------------------------------------------
// Constantes
// -----------------------------------------------------------------------------

const SPLIT_VIEW_SIZE = 200;

const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau', contacted: 'Contacte', qualified: 'Qualifie',
  unqualified: 'Non qualifie', nurturing: 'Nurturing',
};

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-slate-100 text-slate-600',
  contacted: 'bg-blue-50 text-blue-700',
  qualified: 'bg-emerald-50 text-emerald-700',
  unqualified: 'bg-red-50 text-red-600',
  nurturing: 'bg-amber-50 text-amber-700',
};

const STAGE_LABELS: Record<string, string> = {
  new: 'Nouveau', contacted: 'Contacte', meeting: 'Meeting',
  proposal: 'Proposition', negotiation: 'Negociation',
  won: 'Gagne', lost: 'Perdu',
};

const STAGE_COLORS: Record<string, string> = {
  new: 'bg-slate-100 text-slate-600',
  contacted: 'bg-blue-50 text-blue-700',
  meeting: 'bg-indigo-50 text-indigo-700',
  proposal: 'bg-amber-50 text-amber-700',
  negotiation: 'bg-orange-50 text-orange-700',
  won: 'bg-emerald-50 text-emerald-700',
  lost: 'bg-red-50 text-red-600',
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

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [listSearch, setListSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'activity' | 'deals' | 'tasks'>('activity');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [composeEmailOpen, setComposeEmailOpen] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerChannel, setComposerChannel] = useState<ComposerChannel>('note');

  const { data: contactsList } = useQuery({
    queryKey: ['contacts', { search: listSearch, size: SPLIT_VIEW_SIZE }],
    queryFn: () => getContacts({ search: listSearch, size: SPLIT_VIEW_SIZE }),
  });

  const { data: contact, isLoading } = useQuery({
    queryKey: ['contact', id],
    queryFn: () => getContact(id!),
    enabled: !!id,
  });

  const { data: activitiesData } = useQuery({
    queryKey: ['activities', { contact_id: id }],
    queryFn: () => getActivities({ contact_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: dealsData } = useQuery({
    queryKey: ['deals', { contact_id: id }],
    queryFn: () => getDeals({ contact_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: tasksData } = useQuery({
    queryKey: ['tasks', { contact_id: id }],
    queryFn: () => getTasks({ contact_id: id, size: 50 }),
    enabled: !!id,
  });

  // AI next-action contextuel
  const { data: nextAction, isLoading: nextActionLoading } = useQuery({
    queryKey: ['next-action', 'contact', id],
    queryFn: () => getContactNextAction(id!),
    enabled: !!id,
    retry: false,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteContact(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contacts'] });
      navigate('/contacts');
    },
  });

  const contacts: Contact[] = useMemo(() => contactsList?.items ?? [], [contactsList]);
  const activities: Activity[] = useMemo(() => activitiesData?.items ?? [], [activitiesData]);
  const deals: Deal[] = useMemo(() => dealsData?.items ?? [], [dealsData]);
  const tasks: Task[] = useMemo(() => tasksData?.items ?? [], [tasksData]);

  // KPI : Task.is_completed (pas .status — DC10) ; pipeline = deals non clos
  const kpi = useMemo(() => {
    const pipeline = deals.filter((d) => !['won', 'lost'].includes(d.stage))
      .reduce((sum, d) => sum + (d.amount ?? 0), 0);
    const wonAmount = deals.filter((d) => d.stage === 'won')
      .reduce((sum, d) => sum + (d.amount ?? 0), 0);
    const openTasks = tasks.filter((t) => !t.is_completed).length;
    const lastActivity = activities[0]?.created_at;
    return { pipeline, wonAmount, openTasks, lastActivity };
  }, [deals, tasks, activities]);

  if (isLoading || !contact) {
    return <div className="flex items-center justify-center h-full"><LoadingSpinner /></div>;
  }

  const initials = ((contact.first_name?.[0] ?? '') + (contact.last_name?.[0] ?? '')).toUpperCase();

  const handleAiAction = (action: NextActionAction) => {
    if (action.type === 'compose_email') {
      setComposeEmailOpen(true);
    } else if (action.type === 'create_task') {
      // Pour cette PR, on log via composer. Une vraie modale tache existe deja
      // mais elle est integree directement dans la timeline.
      setComposerChannel('note');
      setComposerOpen(true);
    }
    // snooze/view : no-op pour l'instant (DC17)
  };

  return (
    <div className="flex h-full bg-slate-50">

      {/* ===== LISTE ===== */}
      <aside className="w-[340px] border-r border-slate-200 bg-white flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-slate-100 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <h2 className="text-lg font-semibold text-slate-900">Contacts</h2>
              <span className="text-xs text-slate-400 tabular-nums">{contacts.length}</span>
            </div>
            <div className="flex gap-1">
              <button className="p-1.5 rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                <Filter className="w-4 h-4" />
              </button>
              <Link to="/contacts" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-primary-600 text-white text-xs font-medium hover:bg-primary-700">
                <Plus className="w-3.5 h-3.5" /> Nouveau
              </Link>
            </div>
          </div>
          <div className="flex items-center gap-2 px-2.5 h-8 bg-slate-50 border border-slate-100 rounded-md">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              value={listSearch}
              onChange={(e) => setListSearch(e.target.value)}
              placeholder="Rechercher..."
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {contacts.map((c) => {
            const ci = ((c.first_name?.[0] ?? '') + (c.last_name?.[0] ?? '')).toUpperCase();
            return (
              <Link
                key={c.id}
                to={`/contacts/${c.id}`}
                className={clsx(
                  'flex items-center gap-3 p-2.5 rounded-lg transition-colors mb-0.5',
                  c.id === id ? 'bg-slate-50 shadow-sm' : 'hover:bg-slate-50'
                )}
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center text-xs font-semibold text-primary-700 flex-shrink-0">
                  {ci}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-800 truncate">{c.first_name} {c.last_name}</div>
                  <div className="text-xs text-slate-400 truncate">{c.title || '—'}</div>
                </div>
                {c.is_decision_maker && (
                  <Star className="w-3 h-3 text-amber-500 fill-amber-500 flex-shrink-0" />
                )}
              </Link>
            );
          })}
        </div>
      </aside>

      {/* ===== DETAIL ===== */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="flex items-center gap-2 px-6 h-11 border-b border-slate-200 bg-white">
          <Link to="/contacts" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded">
            <ArrowLeft className="w-3.5 h-3.5" /> Tous
          </Link>
          {contact.company_id && contact.company_name && (
            <>
              <ChevronRight className="w-3 h-3 text-slate-300" />
              <Link to={`/companies/${contact.company_id}`} className="text-xs text-slate-500 hover:text-slate-700">
                {contact.company_name}
              </Link>
            </>
          )}
          <div className="flex-1" />
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"><Copy className="w-3.5 h-3.5" /></button>
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"><ExternalLink className="w-3.5 h-3.5" /></button>
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"><MoreHorizontal className="w-3.5 h-3.5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-[1100px] mx-auto px-7 py-5 pb-16">

            {/* HEADER */}
            <div className="space-y-5 pb-6 border-b border-slate-200">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-50 to-indigo-100 border border-blue-200/50 flex items-center justify-center text-lg font-semibold text-primary-700">
                  {initials}
                </div>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="text-[11px] uppercase tracking-wider font-medium text-slate-400">
                    Contact · {STATUS_LABELS[contact.status] ?? contact.status}
                  </div>
                  <h1 className="text-2xl font-semibold text-slate-900 tracking-tight flex items-center gap-3 flex-wrap">
                    {contact.first_name} {contact.last_name}
                    {contact.is_decision_maker && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-xs font-medium">
                        <Star className="w-3 h-3 fill-amber-500 text-amber-500" />
                        Decisionnaire
                      </span>
                    )}
                  </h1>
                  <div className="flex items-center gap-2 flex-wrap text-sm text-slate-500">
                    {contact.title && (
                      <span className="inline-flex items-center gap-1">
                        <Briefcase className="w-3 h-3" />
                        {contact.title}
                      </span>
                    )}
                    {contact.company_name && contact.company_id && (
                      <>
                        <span className="text-slate-300">·</span>
                        <Link to={`/companies/${contact.company_id}`} className="inline-flex items-center gap-1 hover:text-primary-600">
                          <Building2 className="w-3 h-3" />
                          {contact.company_name}
                        </Link>
                      </>
                    )}
                    {contact.department && (
                      <>
                        <span className="text-slate-300">·</span>
                        <span>{contact.department}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {contact.email && (
                    <Button variant="secondary" size="sm" icon={Mail} onClick={() => setComposeEmailOpen(true)}>
                      Email
                    </Button>
                  )}
                  {contact.phone && (
                    <a
                      href={`tel:${contact.phone}`}
                      className="inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-colors disabled:opacity-50 bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 px-3 py-1.5 text-xs"
                    >
                      <Phone className="w-4 h-4" />
                      Appeler
                    </a>
                  )}
                  <Button variant="primary" size="sm" icon={Edit2} onClick={() => setEditOpen(true)}>
                    Modifier
                  </Button>
                  <button onClick={() => setDeleteOpen(true)} className="p-1.5 rounded text-slate-400 hover:bg-red-50 hover:text-red-600">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* KPI strip */}
              <div className="grid grid-cols-4 gap-px bg-slate-200 rounded-xl overflow-hidden border border-slate-200">
                <Kpi icon={Target} label="Pipeline" value={`${(kpi.pipeline / 1000).toFixed(1)}`} suffix="k EUR" trend={`${deals.length} deal${deals.length > 1 ? 's' : ''}`} />
                <Kpi icon={TrendingUp} label="Gagne" value={`${(kpi.wonAmount / 1000).toFixed(1)}`} suffix="k EUR" trend="LTV estimee" />
                <Kpi icon={ListTodo} label="Taches" value={String(kpi.openTasks)} suffix={`/ ${tasks.length}`} trend="ouvertes" />
                <Kpi icon={ActivityIcon} label="Derniere activite" value={kpi.lastActivity ? formatRelative(kpi.lastActivity) : '—'} trend={`${activities.length} au total`} />
              </div>
            </div>

            {/* GRID */}
            <div className="grid grid-cols-[1fr_320px] gap-6 pt-5">
              <div className="min-w-0 flex flex-col gap-4">

                <AiCard
                  data={nextAction}
                  loading={nextActionLoading}
                  onAction={handleAiAction}
                />

                {/* Tabs */}
                <div className="flex items-center gap-0.5 border-b border-slate-200 px-1 mt-2">
                  <Tab active={activeTab === 'activity'} onClick={() => setActiveTab('activity')} icon={ActivityIcon} label="Activite" count={activities.length} />
                  <Tab active={activeTab === 'deals'} onClick={() => setActiveTab('deals')} icon={Target} label="Deals" count={deals.length} />
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
                  {activeTab === 'deals' && <DealsList deals={deals} />}
                  {activeTab === 'tasks' && <TasksList tasks={tasks} />}
                </div>
              </div>

              {/* SIDE */}
              <div className="flex flex-col gap-4">
                <Card title="Coordonnees">
                  <div className="-mx-4 -my-4">
                    <SideLink icon={Mail} label="Email" value={contact.email} href={contact.email ? `mailto:${contact.email}` : null} />
                    <SideLink icon={Phone} label="Telephone" value={contact.phone} href={contact.phone ? `tel:${contact.phone}` : null} />
                    <SideLink icon={Linkedin} label="LinkedIn" value={contact.linkedin_url ? 'Voir profil' : null} href={contact.linkedin_url} />
                    <SideLink icon={Building2} label="Entreprise" value={contact.company_name} href={contact.company_id ? `/companies/${contact.company_id}` : null} internal />
                  </div>
                </Card>

                <Card title="Profil">
                  <div className="space-y-2 text-xs">
                    <Row label="Statut">
                      <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', STATUS_COLORS[contact.status])}>
                        {STATUS_LABELS[contact.status] ?? contact.status}
                      </span>
                    </Row>
                    {contact.job_level && <Row label="Seniorite"><span className="text-slate-700">{contact.job_level}</span></Row>}
                    {contact.department && <Row label="Departement"><span className="text-slate-700">{contact.department}</span></Row>}
                    {contact.source && <Row label="Source"><span className="text-slate-700">{contact.source}</span></Row>}
                    <Row label="Cree"><span className="text-slate-700">{formatDate(contact.created_at)}</span></Row>
                    <Row label="Modifie"><span className="text-slate-700">{formatDate(contact.updated_at)}</span></Row>
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
        title="Supprimer ce contact ?"
        message={`Voulez-vous vraiment supprimer ${contact.full_name} ? Cette action est irreversible.`}
        confirmLabel="Supprimer"
        loading={deleteMutation.isPending}
      />

      {/* Edition contact (utilise le ContactForm existant) */}
      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Modifier le contact" size="lg">
        <ContactForm
          contact={contact}
          onSuccess={() => {
            setEditOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['contact', id] });
            void queryClient.invalidateQueries({ queryKey: ['contacts'] });
          }}
          onCancel={() => setEditOpen(false)}
        />
      </Modal>

      {/* Envoi d'email reel via SMTP */}
      <ComposeModal
        open={composeEmailOpen}
        onClose={() => setComposeEmailOpen(false)}
        prefilledContact={contact}
      />

      {/* Composer multi-canal (note/email-log/appel/RDV) */}
      <ComposerModal
        open={composerOpen}
        onClose={() => setComposerOpen(false)}
        initialChannel={composerChannel}
        contactId={id}
      />
    </div>
  );
}

// -----------------------------------------------------------------------------
// Sub-components
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

function Card({ title, icon: Icon, action, children }: {
  title: string; icon?: React.ElementType; action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          {Icon && <Icon className="w-3.5 h-3.5" />}{title}
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function Tab({ active, onClick, icon: Icon, label, count }: {
  active: boolean; onClick: () => void; icon: React.ElementType; label: string; count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium rounded-t-md relative transition-colors',
        active ? 'text-slate-900' : 'text-slate-500 hover:text-slate-700',
      )}
    >
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
      <div className="text-sm font-medium text-slate-800 truncate max-w-[160px]">
        {value || <span className="text-slate-300">—</span>}
      </div>
    </>
  );
  if (href && value) {
    if (internal) {
      return <Link to={href} className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors text-primary-600">{content}</Link>;
    }
    return <a href={href} target={href.startsWith('tel:') || href.startsWith('mailto:') ? undefined : '_blank'} rel="noopener noreferrer" className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors text-primary-600">{content}</a>;
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

function DealsList({ deals }: { deals: Deal[] }) {
  if (deals.length === 0) return <EmptyTab icon={Target} text="Aucun deal lie" />;
  return (
    <div>
      {deals.map((d) => (
        <Link key={d.id} to={`/pipeline/${d.id}`}
          className="grid grid-cols-[1fr_auto_auto_auto] gap-3 items-center px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50/60 transition-colors">
          <div>
            <div className="text-sm font-medium text-slate-800">{d.title}</div>
            <div className="text-xs text-slate-400 mt-0.5">Cloture {d.expected_close_date ? formatDate(d.expected_close_date) : '—'}</div>
          </div>
          <span className={clsx('inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium', STAGE_COLORS[d.stage])}>
            {STAGE_LABELS[d.stage]}
          </span>
          <div className="text-right">
            <div className="text-sm font-semibold text-slate-900 tabular-nums">{(d.amount ?? 0).toLocaleString('fr-FR')} {d.currency}</div>
            <div className="text-xs text-slate-400 mt-0.5">{d.probability ?? 0}%</div>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-300" />
        </Link>
      ))}
    </div>
  );
}

function TasksList({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) return <EmptyTab icon={ListTodo} text="Aucune tache" />;
  return (
    <div>
      {tasks.map((t) => {
        // DC10 — Task expose `is_completed` (pas .status)
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
function formatRelative(d?: string | null) {
  if (!d) return '—';
  const diff = Date.now() - new Date(d).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "aujourd'hui";
  if (days === 1) return 'hier';
  if (days < 30) return `il y a ${days} j`;
  return formatDate(d);
}
