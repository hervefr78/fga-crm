// =============================================================================
// FGA CRM - Company : colonne principale de la fiche detail
// (extrait de CompanyDetail.tsx — JSX iso-comportement, meme rendu DOM)
// Regroupe : AiCard, banniere audit SR, cartes "A propos"/"Derniere levee",
// barre d'onglets et dispatch de contenu (activite / deals / contacts / taches
// / audit). Purement presentationnel : queries & mutations restent dans la page.
// =============================================================================

import {
  Target, Users, ListTodo, Activity as ActivityIcon,
  Zap, TrendingUp, Plus, FileText, Edit2,
} from 'lucide-react';

import type {
  Company, Contact, Deal, Activity,
  NextActionResponse, NextActionAction,
  AuditGenerateStatus, CompanyAuditResponse,
} from '../../types';
import { Badge, Button } from '../ui';
import AiCard from '../ai/AiCard';
import { ComposerChannel } from '../activities/ComposerModal';
import { formatAmountMillions, formatDateFR } from '../../utils/format';
import { Card, Tab, EmptyTab } from './CompanyAtoms';
import ActivityFeed from './CompanyActivityFeed';
import { DealsList, ContactsList } from './CompanyLists';
import { CompanyContactsEmpty } from './CompanyContactsEmpty';
import AuditTab from './CompanyAuditTab';
import CompanyAuditBanner from './CompanyAuditBanner';
import type { EnrichmentJobStatus } from '../../types/enrichment';

// Onglets de la colonne principale (partages avec la page pour typer l'etat,
// evite la duplication de l'union — DC8).
export type CompanyTab = 'activity' | 'deals' | 'contacts' | 'tasks' | 'audit';
export type AuditSubTab = 'messaging' | 'detailed' | 'geo';

interface CompanyMainColumnProps {
  // AiCard (next best action)
  nextAction: NextActionResponse | null | undefined;
  nextActionLoading: boolean;
  onAiAction: (action: NextActionAction) => void;
  // Banniere de statut generation/import d'audit SR
  isGeneratingAudit: boolean;
  auditGenStatus: AuditGenerateStatus | undefined;
  importSuccess: boolean;
  importResult: CompanyAuditResponse | undefined;
  importError: boolean;
  importErrorMessage?: string;
  // Cartes "A propos" / "Derniere levee"
  company: Company;
  onEditDescription: () => void;
  // Onglets + contenu
  activeTab: CompanyTab;
  onTabChange: (tab: CompanyTab) => void;
  auditSubTab: AuditSubTab;
  onAuditSubTabChange: (tab: AuditSubTab) => void;
  contacts: Contact[];
  deals: Deal[];
  nonAuditActivities: Activity[];
  auditActivities: Activity[];
  messagingAudits: Activity[];
  detailedAudits: Activity[];
  geoAudits: Activity[];
  canAudit: boolean;
  isAuditBusy: boolean;
  onNewContact: () => void;
  onNewDeal: () => void;
  onOpenComposer: (channel: ComposerChannel) => void;
  onLaunchAudit: () => void;
  // Recherche des decideurs (enrichissement Icypeas) — CTA de l'onglet Contacts vide.
  onEnrichContacts: () => void;
  contactEnrich: {
    isEnriching: boolean;
    lastStatus: EnrichmentJobStatus | null;
    quotaExceeded: boolean;
    isError: boolean;
  };
}

export default function CompanyMainColumn({
  nextAction,
  nextActionLoading,
  onAiAction,
  isGeneratingAudit,
  auditGenStatus,
  importSuccess,
  importResult,
  importError,
  importErrorMessage,
  company,
  onEditDescription,
  activeTab,
  onTabChange,
  auditSubTab,
  onAuditSubTabChange,
  contacts,
  deals,
  nonAuditActivities,
  auditActivities,
  messagingAudits,
  detailedAudits,
  geoAudits,
  canAudit,
  isAuditBusy,
  onNewContact,
  onNewDeal,
  onOpenComposer,
  onLaunchAudit,
  onEnrichContacts,
  contactEnrich,
}: CompanyMainColumnProps) {
  return (
    <div className="min-w-0 flex flex-col gap-4">

      {/* AI suggestion (branchee sur l'API reelle) */}
      <AiCard
        data={nextAction}
        loading={nextActionLoading}
        onAction={onAiAction}
      />

      {/* Statut generation / import d'audit SR (banniere) */}
      <CompanyAuditBanner
        isGeneratingAudit={isGeneratingAudit}
        auditGenStatus={auditGenStatus}
        importSuccess={importSuccess}
        importResult={importResult}
        importError={importError}
        importErrorMessage={importErrorMessage}
      />

      {/* Description */}
      {company.description && (
        <Card title="A propos" icon={FileText} action={
          <button
            onClick={onEditDescription}
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
        <Tab active={activeTab === 'activity'} onClick={() => onTabChange('activity')} icon={ActivityIcon} label="Activite" count={nonAuditActivities.length} />
        <Tab active={activeTab === 'deals'} onClick={() => onTabChange('deals')} icon={Target} label="Deals" count={deals.length} />
        <Tab active={activeTab === 'contacts'} onClick={() => onTabChange('contacts')} icon={Users} label="Contacts" count={contacts.length} />
        <Tab active={activeTab === 'tasks'} onClick={() => onTabChange('tasks')} icon={ListTodo} label="Taches" />
        {(canAudit || auditActivities.length > 0) && (
          <Tab active={activeTab === 'audit'} onClick={() => onTabChange('audit')} icon={Zap} label="Audit SR" count={auditActivities.length} />
        )}
        <div className="flex-1" />
        {activeTab === 'contacts' && (
          <Button variant="secondary" size="sm" icon={Plus} className="mb-1" onClick={onNewContact}>
            Ajouter
          </Button>
        )}
        {activeTab === 'deals' && (
          <Button variant="secondary" size="sm" icon={Plus} className="mb-1" onClick={onNewDeal}>
            Ajouter
          </Button>
        )}
        {activeTab === 'activity' && (
          <Button variant="secondary" size="sm" icon={Plus} className="mb-1" onClick={() => onOpenComposer('note')}>
            Ajouter
          </Button>
        )}
      </div>

      <div className="bg-white border border-slate-200 border-t-0 rounded-b-xl rounded-t-none -mt-4 overflow-hidden">
        {activeTab === 'activity' && (
          <ActivityFeed
            activities={nonAuditActivities}
            onChannelClick={onOpenComposer}
          />
        )}
        {activeTab === 'deals' && <DealsList deals={deals} />}
        {activeTab === 'contacts' &&
          (contacts.length === 0 ? (
            <CompanyContactsEmpty
              hasSiren={!!company.siren}
              isEnriching={contactEnrich.isEnriching}
              lastStatus={contactEnrich.lastStatus}
              quotaExceeded={contactEnrich.quotaExceeded}
              isError={contactEnrich.isError}
              onEnrich={onEnrichContacts}
            />
          ) : (
            <ContactsList contacts={contacts} />
          ))}
        {activeTab === 'tasks' && <EmptyTab icon={ListTodo} text="Pas de tache pour cette fiche" />}
        {activeTab === 'audit' && (
          <AuditTab
            subTab={auditSubTab}
            onSubTabChange={onAuditSubTabChange}
            messaging={messagingAudits}
            detailed={detailedAudits}
            geo={geoAudits}
            canAudit={canAudit}
            auditPending={isAuditBusy}
            onLaunchAudit={onLaunchAudit}
          />
        )}
      </div>
    </div>
  );
}
