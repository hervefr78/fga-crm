// =============================================================================
// FGA CRM - Companies : barre d'actions groupees (selection multiple)
// =============================================================================
// Deux modes :
//  - Selection : "N selectionnees" + boutons [Lancer l'audit] [Chercher les contacts].
//  - En cours / termine : progression "X/N terminés" + statut par entreprise.
// =============================================================================

import clsx from 'clsx';
import {
  Sparkles, Search, X, Loader2, Check, AlertTriangle, MinusCircle,
} from 'lucide-react';

import { Button } from '../ui';
import type { BulkTask, useCompanyBulkAction } from './useCompanyBulkAction';

interface CompanyBulkActionBarProps {
  selectedCount: number;
  // Audit SR reserve aux managers/admins (endpoints backend manager-gated).
  canAudit: boolean;
  onAudit: () => void;
  onContacts: () => void;
  onClear: () => void;
  bulk: ReturnType<typeof useCompanyBulkAction>;
}

export default function CompanyBulkActionBar({
  selectedCount, canAudit, onAudit, onContacts, onClear, bulk,
}: CompanyBulkActionBarProps) {
  const { action, tasks, summary, isRunning, reset } = bulk;

  // ---- Mode progression (action lancee) ----
  if (action) {
    const label = action === 'audit' ? 'Audit' : 'Recherche de contacts';
    const finished = summary.done + summary.failed;
    const target = summary.total - summary.skipped;
    return (
      <div className="rounded-xl border border-primary-100 bg-primary-50/40 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-medium text-slate-800">
            {isRunning
              ? <Loader2 className="w-4 h-4 text-primary-600 animate-spin shrink-0" />
              : <Check className="w-4 h-4 text-emerald-600 shrink-0" />}
            <span>{label} : {finished}/{target} termine{finished > 1 ? 's' : ''}</span>
            {summary.skipped > 0 && (
              <span className="text-xs font-normal text-slate-400">
                · {summary.skipped} ignoree{summary.skipped > 1 ? 's' : ''} (pas de lien SR)
              </span>
            )}
            {summary.failed > 0 && (
              <span className="text-xs font-normal text-red-500">
                · {summary.failed} echec{summary.failed > 1 ? 's' : ''}
              </span>
            )}
          </div>
          {/* Toujours actif : masquer le suivi n'annule pas les jobs (ils
              continuent cote serveur, le resultat apparait sur chaque fiche). */}
          <Button
            variant="secondary" size="sm" icon={X}
            onClick={() => { reset(); onClear(); }}
          >
            {isRunning ? 'Masquer' : 'Fermer'}
          </Button>
        </div>

        <div className="mt-2 flex flex-wrap gap-1.5">
          {tasks.map((t) => <TaskChip key={t.id} task={t} />)}
        </div>
      </div>
    );
  }

  // ---- Mode selection ----
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <span className="text-sm text-slate-600">
        <span className="font-medium text-slate-800">{selectedCount}</span>
        {' '}entreprise{selectedCount > 1 ? 's' : ''} selectionnee{selectedCount > 1 ? 's' : ''}
      </span>
      <div className="flex items-center gap-2">
        {canAudit && (
          <Button variant="secondary" size="sm" icon={Sparkles} onClick={onAudit}>
            Lancer l'audit
          </Button>
        )}
        <Button variant="secondary" size="sm" icon={Search} onClick={onContacts}>
          Chercher les contacts
        </Button>
        <button
          onClick={onClear}
          className="p-1.5 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          aria-label="Deselectionner"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

const STATUS_META = {
  running: { icon: Loader2, cls: 'text-primary-600', spin: true },
  done: { icon: Check, cls: 'text-emerald-600', spin: false },
  failed: { icon: AlertTriangle, cls: 'text-red-500', spin: false },
  skipped: { icon: MinusCircle, cls: 'text-slate-300', spin: false },
} as const;

function TaskChip({ task }: { task: BulkTask }) {
  const meta = STATUS_META[task.status];
  const Icon = meta.icon;
  return (
    <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] text-slate-600">
      <Icon className={clsx('w-3 h-3 shrink-0', meta.cls, meta.spin && 'animate-spin')} />
      <span className="max-w-[130px] truncate">{task.name}</span>
    </span>
  );
}
