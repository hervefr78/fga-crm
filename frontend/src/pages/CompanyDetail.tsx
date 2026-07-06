// =============================================================================
// FGA CRM - Page detail Entreprise (v2 - refonte UI)
// Split-view + KPI strip + AI suggestions + timeline activite + Audit SR
// =============================================================================

import { useState, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Globe, Phone, Linkedin, MapPin,
  Copy, ExternalLink, MoreHorizontal,
  Plus, Filter, Search,
} from 'lucide-react';
import clsx from 'clsx';

import {
  getCompany, getCompanies, getContacts, getDeals, getActivities,
  deleteCompany, triggerCompanyAudit, getCompanyNextAction,
} from '../api/client';
import type {
  Company, Contact, Deal, Activity, CompanyAuditResponse,
  NextActionAction,
} from '../types';
import { ConfirmDialog, LoadingSpinner, Modal } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';
import ContactForm from '../components/contacts/ContactForm';
import DealForm from '../components/pipeline/DealForm';
import ComposerModal, { ComposerChannel } from '../components/activities/ComposerModal';
import { Card, SideLink, Row } from '../components/company/CompanyAtoms';
import { useCompanyAuditGeneration } from '../components/company/useCompanyAuditGeneration';
import { useCompanyContactEnrichment } from '../components/company/useCompanyContactEnrichment';
import {
  SPLIT_VIEW_SIZE, cleanUrl, formatDate,
} from '../components/company/companyUtils';
import CompanyHeader from '../components/company/CompanyHeader';
import CompanyMainColumn from '../components/company/CompanyMainColumn';
import CompanyTabsSection, {
  CompanyTab, AuditSubTab,
} from '../components/company/CompanyTabsSection';

// -----------------------------------------------------------------------------
// Page
// -----------------------------------------------------------------------------

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [listSearch, setListSearch] = useState('');
  const [activeTab, setActiveTab] = useState<CompanyTab>('activity');
  const [auditSubTab, setAuditSubTab] = useState<AuditSubTab>('messaging');
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
  // Logique portee par le hook useCompanyAuditGeneration. La mutation d'import
  // (auditMutation ci-dessus) est injectee via importAudit / importPending.
  const { mutate: importAudit } = auditMutation;
  const { isGeneratingAudit, auditGenStatus, generateAudit, isAuditBusy } =
    useCompanyAuditGeneration({
      companyId: id,
      importAudit,
      importPending: auditMutation.isPending,
      onGenerateStart: () => setActiveTab('audit'),
    });

  // --- Recherche des decideurs (CEO/CTO/CMO/CPO) via enrichissement Icypeas ---
  // CTA affiche dans l'onglet Contacts : etat vide (aucun contact) OU barre
  // d'enrichissement (contacts existants, ex. decideurs encore sans email).
  const {
    enrich: enrichContacts,
    isEnriching: isEnrichingContacts,
    lastStatus: enrichLastStatus,
    lastEmailsFound: enrichLastEmailsFound,
    quotaExceeded: enrichQuotaExceeded,
    sirenNotFound: enrichSirenNotFound,
    isError: enrichIsError,
  } = useCompanyContactEnrichment({ companyId: id });

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
            <CompanyHeader
              company={company}
              kpi={kpi}
              activityCount={nonAuditActivities.length}
              canAudit={canAudit}
              isAuditBusy={isAuditBusy}
              onEdit={() => setEditOpen(true)}
              onGenerateAudit={() => generateAudit()}
              onNewDeal={() => setDealFormOpen(true)}
              onDelete={() => setDeleteOpen(true)}
            />

            {/* ===== GRID 2 COLONNES ===== */}
            <div className="grid grid-cols-[1fr_320px] gap-6 pt-5">

              {/* COL MAIN */}
              <CompanyMainColumn
                nextAction={nextAction}
                nextActionLoading={nextActionLoading}
                onAiAction={handleAiAction}
                isGeneratingAudit={isGeneratingAudit}
                auditGenStatus={auditGenStatus}
                importSuccess={auditMutation.isSuccess}
                importResult={auditMutation.data}
                importError={auditMutation.isError}
                importErrorMessage={auditMutation.error?.message}
                company={company}
                onEditDescription={() => setEditOpen(true)}
              />

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

            {/* ===== ONGLETS (pleine largeur, sous la grille cartes | side) ===== */}
            <div className="pt-6">
              <CompanyTabsSection
                activeTab={activeTab}
                onTabChange={setActiveTab}
                auditSubTab={auditSubTab}
                onAuditSubTabChange={setAuditSubTab}
                contacts={contacts}
                deals={deals}
                nonAuditActivities={nonAuditActivities}
                auditActivities={auditActivities}
                messagingAudits={messagingAudits}
                detailedAudits={detailedAudits}
                geoAudits={geoAudits}
                canAudit={canAudit}
                isAuditBusy={isAuditBusy}
                onNewContact={() => setContactFormOpen(true)}
                onNewDeal={() => setDealFormOpen(true)}
                onOpenComposer={(c) => { setComposerChannel(c); setComposerOpen(true); }}
                onLaunchAudit={() => generateAudit()}
                onEnrichContacts={enrichContacts}
                contactEnrich={{
                  isEnriching: isEnrichingContacts,
                  lastStatus: enrichLastStatus,
                  lastEmailsFound: enrichLastEmailsFound,
                  quotaExceeded: enrichQuotaExceeded,
                  sirenNotFound: enrichSirenNotFound,
                  isError: enrichIsError,
                }}
              />
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
