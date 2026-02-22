// =============================================================================
// FGA CRM - KPI Card (Dashboard V2)
// =============================================================================

import clsx from 'clsx';

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
}

export default function KpiCard({ title, value, subtitle, icon: Icon, color, bgColor }: KpiCardProps) {
  return (
    <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={clsx('p-2.5 rounded-lg', bgColor)}>
          <Icon className={clsx('w-5 h-5', color)} />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-slate-400 font-medium">{title}</p>
          <p className="text-xl font-bold text-slate-800 mt-0.5 truncate">{value}</p>
          {subtitle && (
            <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
    </div>
  );
}
