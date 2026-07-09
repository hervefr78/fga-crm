// =============================================================================
// FGA CRM - Lead Engine : file d'attente priorisee (ecran 1 de la vision)
// =============================================================================
// Leads mmf_gap tries par profondeur du gap x fraicheur des fonds — le gap
// s'affiche en premier : c'est lui qu'on vend. Actions par lead :
//  - decideurs joignables -> [Drafter] (ou [Voir le draft] si deja genere)
//  - sinon -> [Chercher les décideurs] (enrichissement)
//  - [Écarter] -> signal ignore (memorise, pas de re-nag)
// =============================================================================

import { Loader2, Users } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button, EmptyState, LoadingSpinner } from '../ui';
import type { LeadQueueItem, LeadSignal } from '../../types/leadEngine';
import { fundingQualifier, signalReason } from './leadEngineUtils';

interface LeadQueuePanelProps {
  items: LeadQueueItem[];
  isLoading: boolean;
  busySignalId: string | null;
  onDraft: (signal: LeadSignal) => void;
  onEnrich: (signal: LeadSignal) => void;
  onDismiss: (signal: LeadSignal) => void;
}

export default function LeadQueuePanel({
  items, isLoading, busySignalId, onDraft, onEnrich, onDismiss,
}: LeadQueuePanelProps) {
  if (isLoading) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex justify-center">
        <LoadingSpinner />
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
        <EmptyState
          icon={Users}
          message="File vide — aucun MMF gap à traiter. Les nouveaux signaux arrivent via le scan horaire."
        />
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
      <ul className="divide-y divide-slate-100">
        {items.map(({ signal, contacts_with_email, has_draft }, index) => {
          const busy = busySignalId === signal.id;
          const qualifier = fundingQualifier(signal);
          return (
            <li key={signal.id} className="flex items-center gap-3 px-4 py-3">
              <span className="text-xs text-slate-300 font-medium tabular-nums w-6 shrink-0">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  {signal.company_id ? (
                    <Link
                      to={`/companies/${signal.company_id}`}
                      className="text-sm font-medium text-slate-800 hover:text-primary-600 truncate"
                    >
                      {signal.payload_json.company_name ?? 'Société inconnue'}
                    </Link>
                  ) : (
                    <span className="text-sm font-medium text-slate-800 truncate">
                      {signal.payload_json.company_name ?? 'Société inconnue'}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                    <Users className="w-3 h-3" />
                    {contacts_with_email} joignable{contacts_with_email > 1 ? 's' : ''}
                  </span>
                </div>
                <p className="text-sm text-slate-600 mt-0.5 truncate">
                  {signalReason(signal)}
                  {qualifier && <span className="text-slate-400"> · {qualifier}</span>}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {busy && <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />}
                {!busy && (
                  <>
                    {contacts_with_email > 0 ? (
                      <Button size="sm" onClick={() => onDraft(signal)}>
                        {has_draft ? 'Voir le draft' : 'Drafter'}
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => onEnrich(signal)}>
                        Chercher les décideurs
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => onDismiss(signal)}>
                      Écarter
                    </Button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
