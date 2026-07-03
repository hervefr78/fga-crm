// =============================================================================
// FGA CRM - Page detail Entreprise (v2 - refonte UI)
// Split-view + KPI strip + AI suggestions + timeline activite + Audit SR
// =============================================================================

import { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Globe, Phone, Linkedin, MapPin,
  Edit2, Trash2, Copy, ExternalLink, MoreHorizontal,
  Target, Users, ListTodo, Activity as ActivityIcon,
  Zap, Star, TrendingUp, Plus, Filter, Search,
  FileText, AlertCircle,
} from 'lucide-react';
import clsx from 'clsx';

import {
  getCompany, getCompanies, getContacts, getDeals, getActivities,
  deleteCompany, triggerCompanyAudit, getCompanyNextAction,
  generateCompanyAudit, getCompanyAuditGenerateStatus,
} from '../api/client';
import type {
  Company, Contact, Deal, Activity, CompanyAuditResponse,
  NextActionAction, AuditGenerateStatus,
} from '../types';
import { Badge, Button, ConfirmDialog, LoadingSpinner, Modal } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';
import ContactForm from '../components/contacts/ContactForm';
import DealForm from '../components/pipeline/DealForm';
import AiCard from '../components/ai/AiCard';
import ComposerModal, { ComposerChannel } from '../components/activities/ComposerModal';
import { formatAmountMillions, formatDateFR } from '../utils/format';
import { Kpi, Card, Tab, SideLink, Row, EmptyTab } from '../components/company/CompanyAtoms';
import ActivityFeed from '../components/company/CompanyActivityFeed';
import { DealsList, ContactsList } from '../components/company/CompanyLists';
import AuditTab from '../components/company/CompanyAuditTab';
import {
  SPLIT_VIEW_SIZE, cleanUrl, formatDate, formatRelative,
} from '../components/company/companyUtils';

// -----------------------------------------------------------------------------
// Page
// -----------------------------------------------------------------------------

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [listSearch, setListSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'activity' | 'deals' | 'contacts' | 'tasks' | 'audit'>('activity');
  const [auditSubTab, setAuditSubTab] = useState<'messaging' | 'detailed' | 'geo'>('messaging');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [contactFormOpen, setContactFormOpen] = useState(false);
  const [dealFormOpen, setDealFormOpen] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerChannel, setComposerChannel] = useState<ComposerChannel>('note');

  // Liste pour le split-view (DC1 — size borne)
  const { data: companiesList } = useQuery({
    queryKey: ['companies', { search: listSearch, size: SPLIT_VIEW_SIZE }],
    queryFn: () => getCompanies({ search: listSearch, size: SPLIT_VIEW_SIZE }),
  });

  const { data: company, isLoading } = useQuery({
    queryKey: ['company', id],
    queryFn: () => getCompany(id!),
    enabled: !!id,
  });

  const { data: contactsData } = useQuery({
    queryKey: ['contacts', { company_id: id }],
    queryFn: () => getContacts({ company_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: dealsData } = useQuery({
    queryKey: ['deals', { company_id: id }],
    queryFn: () => getDeals({ company_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: activitiesData } = useQuery({
    queryKey: ['activities', { company_id: id }],
    queryFn: () => getActivities({ company_id: id, size: 50 }),
    enabled: !!id,
  });

  // AI next-action : retry: false pour eviter de spam le backend si endpoint
  // indispo (DC7 — fallback graceful : la card ne s'affiche pas si error/null).
  const { data: nextAction, isLoading: nextActionLoading } = useQuery({
    queryKey: ['next-action', 'company', id],
    queryFn: () => getCompanyNextAction(id!),
    enabled: !!id,
    retry: false,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCompany(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
      navigate('/companies');
    },
  });

  // Import d'un audit SR existant (pull du resultat deja calcule cote SR)
  const auditMutation = useMutation<CompanyAuditResponse, Error>({
    mutationFn: () => triggerCompanyAudit(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['activities', { company_id: id }] });
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
      setActiveTab('audit');
    },
  });

  // --- Generation d'audit a la demande : trigger SR -> poll -> import auto ---
  const [isGeneratingAudit, setIsGeneratingAudit] = useState(false);
  const { mutate: importAudit } = auditMutation;

  const generateAuditMutation = useMutation({
    mutationFn: () => generateCompanyAudit(id!),
    onSuccess: () => {
      setIsGeneratingAudit(true);
      setActiveTab('audit');
    },
    onError: (err) => {
      // 409 = un audit tourne deja cote SR -> on poll quand meme
      if ((err as { response?: { status?: number } })?.response?.status === 409) {
        setIsGeneratingAudit(true);
        setActiveTab('audit');
      }
    },
  });

  const { data: auditGenStatus } = useQuery<AuditGenerateStatus>({
    queryKey: ['audit-generate-status', id],
    queryFn: () => getCompanyAuditGenerateStatus(id!),
    enabled: isGeneratingAudit && !!id,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'completed' || s === 'failed' ? false : 5000;
    },
  });

  // Transitions du pipeline SR : completed -> importer le resultat ; failed -> stop
  useEffect(() => {
    if (!isGeneratingAudit) return;
    if (auditGenStatus?.status === 'completed') {
      setIsGeneratingAudit(false);
      importAudit();
    } else if (auditGenStatus?.status === 'failed') {
      setIsGeneratingAudit(false);
    }
  }, [auditGenStatus?.status, isGeneratingAudit, importAudit]);

  const auditBusy =
    generateAuditMutation.isPending || isGeneratingAudit || auditMutation.isPending;

  // Memoize les arrays derives pour stabiliser les references (evite les
  // re-render inutiles des sous-composants et stabilise les deps de useMemo).
  const contacts: Contact[] = useMemo(() => contactsData?.items ?? [], [contactsData]);
  const deals: Deal[] = useMemo(() => dealsData?.items ?? [], [dealsData]);
  const activities: Activity[] = useMemo(() => activitiesData?.items ?? [], [activitiesData]);
  const companies: Company[] = useMemo(() => companiesList?.items ?? [], [companiesList]);

  // Separer audits des autres activites (audits = onglet dedie)
  const auditActivities = useMemo(() => activities.filter((a) => a.type === 'audit'), [activities]);
  const nonAuditActivities = useMemo(() => activities.filter((a) => a.type !== 'audit'), [activities]);
  const messagingAudits = useMemo(() => auditActivities.filter((a) => a.metadata_?.audit_type === 'messaging'), [auditActivities]);
  const detailedAudits = useMemo(() => auditActivities.filter((a) => a.metadata_?.audit_type === 'detailed'), [auditActivities]);
  const geoAudits = useMemo(() => auditActivities.filter((a) => a.metadata_?.audit_type === 'geo'), [auditActivities]);

  const canAudit = !!company?.startup_radar_id && !company.startup_radar_id.startsWith('inv:');

  // KPI calcules (DC8 — calcul derive cote front)
  const kpi = useMemo(() => {
    const pipeline = deals.filter((d) => !['won', 'lost'].includes(d.stage))
      .reduce((sum, d) => sum + (d.amount ?? 0), 0);
    const wonAmount = deals.filter((d) => d.stage === 'won')
      .reduce((sum, d) => sum + (d.amount ?? 0), 0);
    const lastActivity = activities[0]?.created_at;
    return { pipeline, wonAmount, lastActivity, dealsCount: deals.length };
  }, [deals, activities]);

  if (isLoading || !company) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner />
      </div>
    );
  }

  // Branchement de l'AI card sur les actions reelles (DC2 — explicit)
  const handleAiAction = (action: NextActionAction) => {
    if (action.type === 'create_task') {
      // Le panneau "Ajouter une tache" est porte par la barre d'onglets ; ici on
      // ouvre directement le composer en mode "note" comme repli (le user pourra
      // enchainer une tache via l'onglet). Pour une vraie modale tache, appeler
      // setTaskOpen(true) une fois la tache modale extraite.
      setComposerChannel('note');
      setComposerOpen(true);
    } else if (action.type === 'compose_email') {
      setComposerChannel('email');
      setComposerOpen(true);
    } else if (action.type === 'snooze' || action.type === 'view') {
      // Snooze : pas de side-effect cote front pour l'instant. View = no-op.
      // (DC17 — fragilite : pas de persistance du snooze. A signaler.)
    }
  };

  return (
    <div className="flex h-full bg-slate-50">

      {/* ======= COLONNE LISTE (split-view) ======= */}
      <aside className="w-[340px] border-r border-slate-200 bg-white flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-slate-100 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <h2 className="text-lg font-semibold text-slate-900">Entreprises</h2>
              <span className="text-xs text-slate-400 tabular-nums">
                {companies.length}
              </span>
            </div>
            <div className="flex gap-1">
              <button className="p-1.5 rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                <Filter className="w-4 h-4" />
              </button>
              <Link to="/companies" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-primary-600 text-white text-xs font-medium hover:bg-primary-700">
                <Plus className="w-3.5 h-3.5" /> Nouvelle
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
          {companies.map((c) => (
            <Link
              key={c.id}
              to={`/companies/${c.id}`}
              className={clsx(
                'flex items-center gap-3 p-2.5 rounded-lg transition-colors mb-0.5',
                c.id === id
                  ? 'bg-slate-50 shadow-sm'
                  : 'hover:bg-slate-50'
              )}
            >
              <div className="w-8 h-8 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600 flex-shrink-0">
                {c.name.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-800 truncate">{c.name}</div>
                <div className="text-xs text-slate-400 truncate">{c.industry || '—'}</div>
              </div>
            </Link>
          ))}
        </div>
      </aside>

      {/* ======= COLONNE DETAIL ======= */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Toolbar */}
        <div className="flex items-center gap-2 px-6 h-11 border-b border-slate-200 bg-white">
          <Link to="/companies" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded">
            <ArrowLeft className="w-3.5 h-3.5" /> Toutes
          </Link>
          {company.industry && <span className="text-xs text-slate-400">{company.industry}</span>}
          <div className="flex-1" />
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <Copy className="w-3.5 h-3.5" />
          </button>
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
          <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <MoreHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-[1100px] mx-auto px-7 py-5 pb-16">

            {/* ===== HEADER ===== */}
            <div className="space-y-5 pb-6 border-b border-slate-200">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 border border-slate-200 flex items-center justify-center text-2xl font-semibold text-slate-600">
                  {company.name.slice(0, 2)}
                </div>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="text-[11px] uppercase tracking-wider font-medium text-slate-400">
                    Entreprise · {company.startup_radar_id ? 'Startup Radar' : 'Manuel'}
                  </div>
                  <h1 className="text-2xl font-semibold text-slate-900 tracking-tight flex items-center gap-3 flex-wrap">
                    {company.name}
                    {company.startup_radar_id && (
                      <Badge variant="success">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1" />
                        Active
                      </Badge>
                    )}
                  </h1>
                  <div className="flex items-center gap-2 flex-wrap text-sm text-slate-500">
                    {company.industry && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md border border-slate-200 text-xs">
                        {company.industry}
                      </span>
                    )}
                    {(company.city || company.country) && (
                      <>
                        <span className="text-slate-300">·</span>
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          {[company.city, company.country].filter(Boolean).join(', ')}
                        </span>
                      </>
                    )}
                    {company.size_range && (
                      <>
                        <span className="text-slate-300">·</span>
                        <span>{company.size_range}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <Button variant="secondary" size="sm" icon={Edit2} onClick={() => setEditOpen(true)}>
                    Modifier
                  </Button>
                  {canAudit && (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={Zap}
                      onClick={() => generateAuditMutation.mutate()}
                      loading={auditBusy}
                    >
                      Audit Startup Radar
                    </Button>
                  )}
                  <Button variant="primary" size="sm" icon={Plus} onClick={() => setDealFormOpen(true)}>
                    Opportunite
                  </Button>
                  <button
                    onClick={() => setDeleteOpen(true)}
                    className="p-1.5 rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* KPI strip */}
              <div className="grid grid-cols-4 gap-px bg-slate-200 rounded-xl overflow-hidden border border-slate-200">
                <Kpi
                  icon={Star}
                  label="Score"
                  value={String(company.audit_score ?? '—')}
                  suffix={company.audit_score ? '/ 100' : ''}
                  trend={company.audit_score ? 'Auditee' : 'Non auditee'}
                />
                <Kpi
                  icon={TrendingUp}
                  label="Gagne"
                  value={`${(kpi.wonAmount / 1000).toFixed(1)}`}
                  suffix="k EUR"
                  trend={kpi.wonAmount > 0 ? 'Cumul' : '—'}
                />
                <Kpi
                  icon={Target}
                  label="Pipeline"
                  value={`${(kpi.pipeline / 1000).toFixed(1)}`}
                  suffix="k EUR"
                  trend={`${kpi.dealsCount} deal${kpi.dealsCount > 1 ? 's' : ''}`}
                />
                <Kpi
                  icon={ActivityIcon}
                  label="Activite 30j"
                  value={String(nonAuditActivities.length)}
                  trend={kpi.lastActivity ? formatRelative(kpi.lastActivity) : 'Aucune'}
                />
              </div>
            </div>

            {/* ===== GRID 2 COLONNES ===== */}
            <div className="grid grid-cols-[1fr_320px] gap-6 pt-5">

              {/* COL MAIN */}
              <div className="min-w-0 flex flex-col gap-4">

                {/* AI suggestion (branchee sur l'API reelle) */}
                <AiCard
                  data={nextAction}
                  loading={nextActionLoading}
                  onAction={handleAiAction}
                />

                {/* Generation d'audit en cours (pipeline SR) */}
                {isGeneratingAudit && (
                  <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-sm text-indigo-700 flex items-center gap-2">
                    <Zap className="w-4 h-4 flex-shrink-0 animate-pulse" />
                    <span>
                      Generation de l'audit en cours cote Startup Radar
                      {auditGenStatus?.step ? ` — ${auditGenStatus.step}` : '...'}
                    </span>
                  </div>
                )}
                {/* Echec de generation */}
                {!isGeneratingAudit && auditGenStatus?.status === 'failed' && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{auditGenStatus.error || 'La generation de l\'audit a echoue.'}</span>
                  </div>
                )}

                {/* Audit feedback (import result) */}
                {!isGeneratingAudit && auditMutation.isSuccess && auditMutation.data && (
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm text-emerald-700">
                    {auditMutation.data.audits_created > 0 && (
                      <span>{auditMutation.data.audits_created} audit{auditMutation.data.audits_created > 1 ? 's' : ''} cree{auditMutation.data.audits_created > 1 ? 's' : ''}</span>
                    )}
                    {auditMutation.data.audits_skipped > 0 && (
                      <span>{auditMutation.data.audits_created > 0 ? ' — ' : ''}{auditMutation.data.audits_skipped} deja existant{auditMutation.data.audits_skipped > 1 ? 's' : ''}</span>
                    )}
                    {auditMutation.data.audits_created === 0 && auditMutation.data.audits_skipped === 0 && (
                      <span>Aucun audit disponible pour cette entreprise</span>
                    )}
                  </div>
                )}
                {auditMutation.isError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{auditMutation.error?.message || 'Erreur lors du lancement de l\'audit'}</span>
                  </div>
                )}

                {/* Description */}
                {company.description && (
                  <Card title="A propos" icon={FileText} action={
                    <button
                      onClick={() => setEditOpen(true)}
                      className="p-1 rounded hover:bg-slate-100"
                      aria-label="Modifier la description"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                  }>
                    <p className="text-sm text-slate-700 leading-relaxed text-pretty">
                      {company.description}
                    </p>
                  </Card>
                )}

                {/* Funding (synced from Startup Radar multi-source pipeline) */}
                {(company.funding_date || company.funding_amount) && (
                  <Card title="Derniere levee detectee" icon={TrendingUp}>
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      {company.funding_amount && (
                        <Badge variant="success">
                          {formatAmountMillions(company.funding_amount)}
                        </Badge>
                      )}
                      {company.funding_series && (
                        <Badge variant="info">{company.funding_series}</Badge>
                      )}
                      {company.funding_date && (
                        <span className="text-xs text-slate-500">
                          {formatDateFR(company.funding_date)}
                        </span>
                      )}
                    </div>
                    {company.funding_sources && company.funding_sources.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 mt-2">
                        <span className="text-[11px] uppercase tracking-wider font-medium text-slate-400 mr-1">
                          Sources
                        </span>
                        {company.funding_sources.map((src: string) => (
                          <Badge key={src} variant="default" className="text-[10px] py-0.5">
                            {src}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {company.siren && (
                      <p className="text-[11px] text-slate-400 mt-2 font-mono">
                        SIREN : {company.siren}
                      </p>
                    )}
                  </Card>
                )}

                {/* Tabs */}
                <div className="flex items-center gap-0.5 border-b border-slate-200 px-1 mt-2">
                  <Tab active={activeTab === 'activity'} onClick={() => setActiveTab('activity')} icon={ActivityIcon} label="Activite" count={nonAuditActivities.length} />
                  <Tab active={activeTab === 'deals'} onClick={() => setActiveTab('deals')} icon={Target} label="Deals" count={deals.length} />
                  <Tab active={activeTab === 'contacts'} onClick={() => setActiveTab('contacts')} icon={Users} label="Contacts" count={contacts.length} />
                  <Tab active={activeTab === 'tasks'} onClick={() => setActiveTab('tasks')} icon={ListTodo} label="Taches" />
                  {(canAudit || auditActivities.length > 0) && (
                    <Tab active={activeTab === 'audit'} onClick={() => setActiveTab('audit')} icon={Zap} label="Audit SR" count={auditActivities.length} />
                  )}
                  <div className="flex-1" />
                  {activeTab === 'contacts' && (
                    <Button variant="secondary" size="sm" icon={Plus} className="mb-1" onClick={() => setContactFormOpen(true)}>
                      Ajouter
                    </Button>
                  )}
                  {activeTab === 'deals' && (
                    <Button variant="secondary" size="sm" icon={Plus} className="mb-1" onClick={() => setDealFormOpen(true)}>
                      Ajouter
                    </Button>
                  )}
                  {activeTab === 'activity' && (
                    <Button variant="secondary" size="sm" icon={Plus} className="mb-1" onClick={() => { setComposerChannel('note'); setComposerOpen(true); }}>
                      Ajouter
                    </Button>
                  )}
                </div>

                <div className="bg-white border border-slate-200 border-t-0 rounded-b-xl rounded-t-none -mt-4 overflow-hidden">
                  {activeTab === 'activity' && (
                    <ActivityFeed
                      activities={nonAuditActivities}
                      onChannelClick={(c) => { setComposerChannel(c); setComposerOpen(true); }}
                    />
                  )}
                  {activeTab === 'deals' && <DealsList deals={deals} />}
                  {activeTab === 'contacts' && <ContactsList contacts={contacts} />}
                  {activeTab === 'tasks' && <EmptyTab icon={ListTodo} text="Pas de tache pour cette fiche" />}
                  {activeTab === 'audit' && (
                    <AuditTab
                      subTab={auditSubTab}
                      onSubTabChange={setAuditSubTab}
                      messaging={messagingAudits}
                      detailed={detailedAudits}
                      geo={geoAudits}
                      canAudit={canAudit}
                      auditPending={auditBusy}
                      onLaunchAudit={() => generateAuditMutation.mutate()}
                    />
                  )}
                </div>
              </div>

              {/* COL SIDE */}
              <div className="flex flex-col gap-4">

                <Card title="Liens & contact">
                  <div className="-mx-4 -my-4">
                    <SideLink icon={Globe} label="Site web" value={company.website ? cleanUrl(company.website) : null} href={company.website} />
                    <SideLink icon={Linkedin} label="LinkedIn" value={company.linkedin_url ? 'Voir profil' : null} href={company.linkedin_url} />
                    <SideLink icon={Phone} label="Telephone" value={company.phone} href={company.phone ? `tel:${company.phone}` : null} />
                    <SideLink icon={MapPin} label="Adresse" value={[company.city, company.country].filter(Boolean).join(', ') || null} />
                  </div>
                </Card>

                <Card title="Meta">
                  <div className="space-y-2 text-xs">
                    <Row label="Source"><span className="text-slate-700">{company.startup_radar_id ? 'Startup Radar' : 'Manuel'}</span></Row>
                    <Row label="Creee"><span className="text-slate-700">{formatDate(company.created_at)}</span></Row>
                    <Row label="Modifiee"><span className="text-slate-700">{formatDate(company.updated_at)}</span></Row>
                    {company.audit_score != null && (
                      <Row label="Score audit"><span className="text-slate-700 font-medium">{company.audit_score}/100</span></Row>
                    )}
                  </div>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ===== Modals & dialogs ===== */}

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
        title="Supprimer cette entreprise ?"
        message={`Voulez-vous vraiment supprimer ${company.name} ? Cette action est irreversible.`}
        confirmLabel="Supprimer"
        loading={deleteMutation.isPending}
      />

      {/* Edition de l'entreprise (utilise le CompanyForm existant) */}
      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Modifier l'entreprise" size="lg">
        <CompanyForm
          company={company}
          onSuccess={() => {
            setEditOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['company', id] });
            void queryClient.invalidateQueries({ queryKey: ['companies'] });
          }}
          onCancel={() => setEditOpen(false)}
        />
      </Modal>

      {/* Ajouter un contact a cette entreprise */}
      <Modal open={contactFormOpen} onClose={() => setContactFormOpen(false)} title="Nouveau contact" size="lg">
        <ContactForm
          defaultCompanyId={id}
          onSuccess={() => {
            setContactFormOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['contacts', { company_id: id }] });
            setActiveTab('contacts');
          }}
          onCancel={() => setContactFormOpen(false)}
        />
      </Modal>

      {/* Ajouter un deal lie a cette entreprise */}
      <Modal open={dealFormOpen} onClose={() => setDealFormOpen(false)} title="Nouvelle opportunite" size="lg">
        <DealForm
          defaultCompanyId={id}
          onSuccess={() => {
            setDealFormOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['deals', { company_id: id }] });
            setActiveTab('deals');
          }}
          onCancel={() => setDealFormOpen(false)}
        />
      </Modal>

      {/* Composer multi-canal (note/email/appel/RDV) */}
      <ComposerModal
        open={composerOpen}
        onClose={() => setComposerOpen(false)}
        initialChannel={composerChannel}
        companyId={id}
      />
    </div>
  );
}
