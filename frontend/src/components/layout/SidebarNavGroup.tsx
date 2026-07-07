// =============================================================================
// FGA CRM - Navigation : groupe depliable de la sidebar + item de lien
// =============================================================================
// Presentation pure : l'etat ouvert/ferme et la persistance sont geres par
// Layout (aria-expanded pour l'accessibilite).
// =============================================================================

import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import clsx from 'clsx';

import type { NavGroup, NavItem } from './navConfig';
import { isActivePath } from './navConfig';

export function NavLinkItem({ item, pathname }: { item: NavItem; pathname: string }) {
  const isActive = isActivePath(pathname, item.href);
  return (
    <Link
      to={item.href}
      className={clsx(
        'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
        isActive
          ? 'bg-primary-50 text-primary-700'
          : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700',
      )}
    >
      <item.icon className={clsx('w-5 h-5 shrink-0', isActive ? 'text-primary-600' : 'text-slate-400')} />
      <span className="truncate">{item.name}</span>
    </Link>
  );
}

export default function SidebarNavGroup({
  group, open, onToggle, pathname,
}: {
  group: NavGroup;
  open: boolean;
  onToggle: () => void;
  pathname: string;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-400 hover:text-slate-600 transition-colors"
      >
        {group.label}
        <ChevronDown className={clsx('w-3.5 h-3.5 transition-transform', !open && '-rotate-90')} />
      </button>
      {open && (
        <div className="space-y-0.5 mb-1">
          {group.items.map((item) => (
            <NavLinkItem key={item.href} item={item} pathname={pathname} />
          ))}
        </div>
      )}
    </div>
  );
}
