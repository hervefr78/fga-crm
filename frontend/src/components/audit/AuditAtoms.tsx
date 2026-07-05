// =============================================================================
// FGA CRM - Audit : atomes UI (ScoreBar, CollapsibleSection)
// (extraits de AuditResultPanel.tsx)
// =============================================================================

import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';

import { scoreBarColor, scoreColor } from './auditUtils';

// ---------------------------------------------------------------------------
// Barre de score
// ---------------------------------------------------------------------------

export function ScoreBar({ label, score, max = 100 }: { label: string; score: number; max?: number }) {
  const pct = Math.min(Math.round((score / max) * 100), 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-600 w-28 flex-shrink-0 truncate">{label}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-2">
        <div
          className={clsx('h-2 rounded-full transition-all duration-500', scoreBarColor(pct))}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={clsx('text-sm font-semibold w-10 text-right', scoreColor(pct))}>{score}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section pliable
// ---------------------------------------------------------------------------

export function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 rounded-lg">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-slate-400" />
          <span>{title}</span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      {open && <div className="px-4 pb-4 border-t border-slate-100 pt-3">{children}</div>}
    </div>
  );
}
