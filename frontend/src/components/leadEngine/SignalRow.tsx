// =============================================================================
// FGA CRM - Lead Engine : ligne de la Signal Inbox
// =============================================================================
// Un signal = sa raison (le gap d'abord — c'est lui qu'on vend), son
// qualificateur de solvabilite, et ses actions 1-clic selon le type :
//  - funding_detected -> [Auditer le message] (P2 : jamais d'outreach direct)
//  - mmf_gap          -> [Chercher les décideurs] (P1 : prepare l'outreach)
// =============================================================================

import clsx from 'clsx';
import { Banknote, Crosshair, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '../ui';
import type { LeadSignal } from '../../types/leadEngine';
import {
  SIGNAL_TYPE_LABELS, STATUS_BADGES, STATUS_LABELS, fundingQualifier,
  signalReason, timeAgo,
} from './leadEngineUtils';

interface SignalRowProps {
  signal: LeadSignal;
  busy: boolean;          // une action est en cours sur ce signal
  onAction: (signal: LeadSignal) => void;
  onIgnore: (signal: LeadSignal) => void;
  onReopen: (signal: LeadSignal) => void;
}

export default function SignalRow({ signal, busy, onAction, onIgnore, onReopen }: SignalRowProps) {
  const isMmf = signal.signal_type === 'mmf_gap';
  const Icon = isMmf ? Crosshair : Banknote;
  const qualifier = isMmf ? fundingQualifier(signal) : null;
  const companyName = signal.payload_json.company_name ?? 'Société inconnue';

  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <div className={clsx(
        'mt-0.5 p-2 rounded-lg shrink-0',
        isMmf ? 'bg-primary-50 text-primary-600' : 'bg-amber-50 text-amber-600',
      )}>
        <Icon className="w-4 h-4" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          {signal.company_id ? (
            <Link
              to={`/companies/${signal.company_id}`}
              className="text-sm font-medium text-slate-800 hover:text-primary-600 truncate"
            >
              {companyName}
            </Link>
          ) : (
            <span className="text-sm font-medium text-slate-800 truncate">{companyName}</span>
          )}
          <span className="text-xs text-slate-400">{SIGNAL_TYPE_LABELS[signal.signal_type]}</span>
          <span className={clsx(
            'text-[11px] px-1.5 py-0.5 rounded-full font-medium',
            STATUS_BADGES[signal.status],
          )}>
            {STATUS_LABELS[signal.status]}
          </span>
        </div>
        <p className="text-sm text-slate-600 mt-0.5 truncate">
          {signalReason(signal)}
          {qualifier && <span className="text-slate-400"> · {qualifier}</span>}
        </p>
        <p className="text-xs text-slate-400 mt-0.5">
          {timeAgo(signal.created_at)}
          {isMmf
            ? ' · le gap justifie un premier contact'
            : ' · à auditer avant tout contact'}
        </p>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {busy && <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />}
        {signal.status === 'new' && !busy && (
          <>
            <Button size="sm" onClick={() => onAction(signal)}>
              {isMmf ? 'Chercher les décideurs' : 'Auditer le message'}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => onIgnore(signal)}>
              Ignorer
            </Button>
          </>
        )}
        {signal.status === 'ignored' && !busy && (
          <Button size="sm" variant="secondary" onClick={() => onReopen(signal)}>
            Réouvrir
          </Button>
        )}
      </div>
    </li>
  );
}
