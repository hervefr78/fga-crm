// =============================================================================
// FGA CRM - Company : composants atomiques (extraits de CompanyDetail.tsx)
// Kpi, Card, Tab, SideLink, Row, EmptyTab
// =============================================================================

import type { ElementType, ReactNode } from 'react';
import { ArrowUpRight } from 'lucide-react';
import clsx from 'clsx';

export function Kpi({ icon: Icon, label, value, suffix, trend }: {
  icon: ElementType; label: string; value: string; suffix?: string; trend?: string;
}) {
  return (
    <div className="bg-white px-4 py-3.5 flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 uppercase tracking-wider">
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl font-semibold text-slate-900 tabular-nums tracking-tight">{value}</span>
        {suffix && <span className="text-xs text-slate-500 font-medium">{suffix}</span>}
      </div>
      {trend && (
        <div className="flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
          <ArrowUpRight className="w-3 h-3" />
          {trend}
        </div>
      )}
    </div>
  );
}

export function Card({ title, icon: Icon, action, children }: {
  title: string; icon?: ElementType; action?: ReactNode; children: ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          {Icon && <Icon className="w-3.5 h-3.5" />}
          {title}
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export function Tab({ active, onClick, icon: Icon, label, count }: {
  active: boolean; onClick: () => void; icon: ElementType; label: string; count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium rounded-t-md relative transition-colors',
        active ? 'text-slate-900' : 'text-slate-500 hover:text-slate-700',
      )}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
      {count != null && (
        <span className={clsx(
          'text-xs px-1.5 py-0.5 rounded-full font-medium',
          active ? 'bg-primary-50 text-primary-700' : 'bg-slate-100 text-slate-500',
        )}>
          {count}
        </span>
      )}
      {active && <span className="absolute left-2 right-2 -bottom-px h-0.5 bg-slate-900 rounded-full" />}
    </button>
  );
}

export function SideLink({ icon: Icon, label, value, href }: {
  icon: ElementType; label: string; value: string | null; href?: string | null;
}) {
  const content = (
    <>
      <div className="w-7 h-7 rounded-md bg-slate-50 flex items-center justify-center text-slate-500 flex-shrink-0">
        <Icon className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1 text-xs text-slate-500">{label}</div>
      <div className="text-sm font-medium text-slate-800 truncate max-w-[160px]">
        {value || <span className="text-slate-300">—</span>}
      </div>
    </>
  );
  if (href && value) {
    return (
      <a href={href.startsWith('http') || href.startsWith('tel:') || href.startsWith('mailto:') ? href : `https://${href}`}
        target={href.startsWith('tel:') || href.startsWith('mailto:') ? undefined : '_blank'}
        rel="noopener noreferrer"
        className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors text-primary-600">
        {content}
      </a>
    );
  }
  return <div className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-50 last:border-0">{content}</div>;
}

export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between text-slate-500">
      <span>{label}</span>
      {children}
    </div>
  );
}

export function EmptyTab({ icon: Icon, text }: { icon: ElementType; text: string }) {
  return (
    <div className="py-10 flex flex-col items-center justify-center text-center text-sm text-slate-400 gap-2">
      <div className="w-9 h-9 rounded-lg bg-slate-50 flex items-center justify-center">
        <Icon className="w-4 h-4" />
      </div>
      {text}
    </div>
  );
}
