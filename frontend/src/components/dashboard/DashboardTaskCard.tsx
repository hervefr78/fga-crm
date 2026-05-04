// =============================================================================
// FGA CRM - DashboardTaskCard : carte sidebar des taches en retard
// =============================================================================
//
// Affiche jusqu'a 5 taches overdue (filtre backend `overdue=true`).
// - Empty state : check + texte si aucune tache en retard (DC5)
// - Loading state : skeleton
// - Items : titre + due_date relative + badge priorite si urgent
// - Header : titre + lien vers /tasks?overdue=true
// =============================================================================

import { Link } from 'react-router-dom';
import { CheckCircle, AlertTriangle, ListTodo } from 'lucide-react';
import clsx from 'clsx';
import { Badge } from '../ui';
import type { Task } from '../../types';

interface DashboardTaskCardProps {
  tasks: Task[];
  loading?: boolean;
}

export default function DashboardTaskCard({ tasks, loading }: DashboardTaskCardProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          <ListTodo className="w-3.5 h-3.5 text-slate-400" />
          Taches en retard
          {tasks.length > 0 && (
            <span className="text-xs text-slate-400 tabular-nums font-normal">
              · {tasks.length}
            </span>
          )}
        </div>
        <Link
          to="/tasks?overdue=true"
          className="text-xs text-primary-600 hover:text-primary-700 font-medium"
        >
          Voir tout →
        </Link>
      </div>

      {loading ? (
        <div className="p-4 space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-10 bg-slate-50 border border-slate-100 rounded-md animate-pulse" />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="py-8 flex flex-col items-center justify-center text-center text-sm text-slate-400 gap-2 px-4">
          <div className="w-9 h-9 rounded-lg bg-slate-50 flex items-center justify-center">
            <CheckCircle className="w-4 h-4" />
          </div>
          Aucune tache en retard
        </div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {tasks.map((t) => (
            <li key={t.id}>
              <Link
                to={`/tasks/${t.id}`}
                className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50/60 transition-colors"
              >
                <AlertTriangle
                  className={clsx(
                    'w-3.5 h-3.5 mt-0.5 flex-shrink-0',
                    t.priority === 'urgent' ? 'text-red-500' : 'text-amber-500',
                  )}
                />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="text-sm font-medium text-slate-800 truncate">
                    {t.title}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="tabular-nums">
                      {formatRelativeOverdue(t.due_date)}
                    </span>
                    {t.priority === 'urgent' && (
                      <Badge variant="danger" className="!px-1.5 !py-0 !text-[10px]">
                        Urgent
                      </Badge>
                    )}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

// Retourne une date relative pour une tache en retard ("il y a 3 j", "hier")
function formatRelativeOverdue(d?: string | null): string {
  if (!d) return 'Sans echeance';
  const due = new Date(d);
  const now = new Date();
  const diffMs = now.getTime() - due.getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days <= 0) return "aujourd'hui";
  if (days === 1) return 'hier';
  if (days < 30) return `il y a ${days} j`;
  return due.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}
