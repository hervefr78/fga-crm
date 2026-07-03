// =============================================================================
// FGA CRM - Liste des taches de la fiche Deal
// Extrait VERBATIM de DealDetail.tsx (refactor C5) — rendu inchange.
// =============================================================================

import { ListTodo, Check } from 'lucide-react';
import clsx from 'clsx';

import type { Task } from '../../types';
import { EmptyTab } from './DealAtoms';
import { formatDate } from './dealUtils';

export default function TasksList({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) return <EmptyTab icon={ListTodo} text="Aucune tache" />;
  return (
    <div>
      {tasks.map((t) => {
        // DC10 — Task expose `is_completed`
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
