// =============================================================================
// FGA CRM - Contact : listes deals & taches (extraites de ContactDetail.tsx)
// =============================================================================

import { Link } from 'react-router-dom';
import { Target, ListTodo, Check, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

import type { Deal, Task } from '../../types';
import { EmptyTab } from './ContactAtoms';
import { STAGE_COLORS, STAGE_LABELS, formatDate } from './contactUtils';

export function DealsList({ deals }: { deals: Deal[] }) {
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

export function TasksList({ tasks }: { tasks: Task[] }) {
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
