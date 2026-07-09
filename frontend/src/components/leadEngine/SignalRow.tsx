// =============================================================================
// FGA CRM - Lead Engine : ligne de la Signal Inbox
// =============================================================================
// Un signal = sa raison (le gap d'abord — c'est lui qu'on vend), son
// qualificateur de solvabilite, et ses actions 1-clic selon le type :
//  - funding_detected -> [Auditer le message] (P2 : jamais d'outreach direct)
//  - mmf_gap          -> [Chercher les décideurs] (P1 : prepare l'outreach)
//  - inbound_new      -> [Qualifier] (P3 : SPICED, on repond, on ne prospecte pas)
// =============================================================================

import clsx from 'clsx';
import { Banknote, Crosshair, FileText, Loader2, UserPlus } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '../ui';
import type { LeadSignal, LeadSignalType } from '../../types/leadEngine';
import {
  SIGNAL_TYPE_LABELS, STATUS_BADGES, STATUS_LABELS, fundingQualifier,
  signalReason, timeAgo,
} from './leadEngineUtils';

const TYPE_ICONS: Record<LeadSignalType, typeof Crosshair> = {
  mmf_gap: Crosshair,
  funding_detected: Banknote,
  inbound_new: UserPlus,
};

const TYPE_ICON_STYLES: Record<LeadSignalType, string> = {
  mmf_gap: 'bg-primary-50 text-primary-600',
  funding_detected: 'bg-amber-50 text-amber-600',
  inbound_new: 'bg-emerald-50 text-emerald-600',
};

const ACTION_LABELS: Record<LeadSignalType, string> = {
  mmf_gap: 'Chercher les décideurs',
  funding_detected: 'Auditer le message',
  inbound_new: 'Qualifier (SPICED)',
};

const TYPE_HINTS: Record<LeadSignalType, string> = {
  mmf_gap: 'le gap justifie un premier contact',
  funding_detected: 'à auditer avant tout contact',
  inbound_new: 'répondre < 24 h',
};

interface SignalRowProps {
  signal: LeadSignal;
  busy: boolean;          // une action est en cours sur ce signal
  onAction: (signal: LeadSignal) => void;
  onIgnore: (signal: LeadSignal) => void;
  onReopen: (signal: LeadSignal) => void;
}

export default function SignalRow({ signal, busy, onAction, onIgnore, onReopen }: SignalRowProps) {
  const isMmf = signal.signal_type === 'mmf_gap';
  const Icon = TYPE_ICONS[signal.signal_type];
  const qualifier = isMmf ? fundingQualifier(signal) : null;
  const companyName = signal.payload_json.company_name
    ?? (signal.signal_type === 'inbound_new' ? signal.payload_json.contact_name : null)
    ?? 'Société inconnue';

  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <div className={clsx(
        'mt-0.5 p-2 rounded-lg shrink-0',
        TYPE_ICON_STYLES[signal.signal_type],
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
          {signal.payload_json.draft && (
            <span className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded-full font-medium bg-violet-50 text-violet-700">
              <FileText className="w-3 h-3" /> Draft prêt
            </span>
          )}
        </div>
        <p className="text-sm text-slate-600 mt-0.5 truncate">
          {signalReason(signal)}
          {qualifier && <span className="text-slate-400"> · {qualifier}</span>}
        </p>
        <p className="text-xs text-slate-400 mt-0.5">
          {timeAgo(signal.created_at)} · {TYPE_HINTS[signal.signal_type]}
        </p>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {busy && <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />}
        {signal.status === 'new' && !busy && (
          <>
            <Button size="sm" onClick={() => onAction(signal)}>
              {ACTION_LABELS[signal.signal_type]}
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
