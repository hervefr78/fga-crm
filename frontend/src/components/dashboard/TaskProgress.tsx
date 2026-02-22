// =============================================================================
// FGA CRM - Task Progress (Dashboard V2)
// =============================================================================

import { AlertTriangle, CheckCircle } from 'lucide-react';

interface TaskProgressProps {
  total: number;
  completed: number;
  overdue: number;
}

export default function TaskProgress({ total, completed, overdue }: TaskProgressProps) {
  const rate = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="space-y-3">
      {/* Barre de progression */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-sm font-medium text-slate-700">Completion</span>
          <span className="text-sm font-bold text-slate-800">{rate}%</span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2.5">
          <div
            className="h-2.5 rounded-full transition-all duration-500 bg-emerald-500"
            style={{ width: `${rate}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1.5 text-emerald-600">
          <CheckCircle className="w-3.5 h-3.5" />
          <span>{completed}/{total} completees</span>
        </div>
        {overdue > 0 && (
          <div className="flex items-center gap-1.5 text-red-500">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{overdue} en retard</span>
          </div>
        )}
      </div>
    </div>
  );
}
