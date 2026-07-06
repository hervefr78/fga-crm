// =============================================================================
// FGA CRM - Company : barre d'onglets + contenu (extrait de CompanyMainColumn)
// =============================================================================
// Section pleine largeur (sous la grille "cartes | side") : onglets Activite /
// Deals / Contacts / Taches / Audit SR et dispatch du contenu. Purement
// presentationnel : queries & mutations restent dans la page.
// =============================================================================

import {
  Target, Users, ListTodo, Activity as ActivityIcon, Zap, Plus,
} from 'lucide-react';

import type { Contact, Deal, Activity } from '../../types';
import { Button } from '../ui';
import { ComposerChannel } from '../activities/ComposerModal';
import { Tab, EmptyTab } from './CompanyAtoms';
import ActivityFeed from './CompanyActivityFeed';
import { DealsList, ContactsList } from './CompanyLists';
import { CompanyContactsEmpty } from './CompanyContactsEmpty';
import { CompanyContactsEnrichBar } from './CompanyContactsEnrichBar';
import AuditTab from './CompanyAuditTab';
import type { EnrichmentJobStatus } from '../../types/enrichment';

// Onglets (partages avec la page pour typer l'etat — DC8).
export type CompanyTab = 'activity' | 'deals' | 'contacts' | 'tasks' | 'audit';
export type AuditSubTab = 'messaging' | 'detailed' | 'geo';

interface CompanyTabsSectionProps {
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
  // Recherche des decideurs (enrichissement Icypeas) — CTA de l'onglet Contacts,
  // affiche a la fois dans l'etat vide et dans la barre (contacts existants).
  onEnrichContacts: () => void;
  contactEnrich: {
    isEnriching: boolean;
    lastStatus: EnrichmentJobStatus | null;
    lastEmailsFound: number | null;
    quotaExceeded: boolean;
    sirenNotFound: boolean;
    isError: boolean;
  };
}

export default function CompanyTabsSection({
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
}: CompanyTabsSectionProps) {
  return (
    <div className="min-w-0">
      {/* Tabs */}
      <div className="flex items-center gap-0.5 border-b border-slate-200 px-1">
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

      <div className="bg-white border border-slate-200 border-t-0 rounded-b-xl rounded-t-none overflow-hidden">
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
              isEnriching={contactEnrich.isEnriching}
              lastStatus={contactEnrich.lastStatus}
              quotaExceeded={contactEnrich.quotaExceeded}
              sirenNotFound={contactEnrich.sirenNotFound}
              isError={contactEnrich.isError}
              onEnrich={onEnrichContacts}
            />
          ) : (
            <>
              {/* Contacts existants : point d'entree permanent pour (re)lancer la
                  recherche des decideurs/emails (complete l'etat vide). */}
              <CompanyContactsEnrichBar
                noEmailCount={contacts.filter((c) => !c.email).length}
                isEnriching={contactEnrich.isEnriching}
                lastStatus={contactEnrich.lastStatus}
                lastEmailsFound={contactEnrich.lastEmailsFound}
                quotaExceeded={contactEnrich.quotaExceeded}
                sirenNotFound={contactEnrich.sirenNotFound}
                isError={contactEnrich.isError}
                onEnrich={onEnrichContacts}
              />
              <ContactsList contacts={contacts} />
            </>
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
