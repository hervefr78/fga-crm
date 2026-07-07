// =============================================================================
// FGA CRM - Layout (Light theme, inspired by Startup Radar)
// =============================================================================
// Sidebar : Dashboard (hors groupe) + groupes depliables Sales / Marketing /
// Reglages (config : navConfig.ts). Etat ouvert/ferme persiste (localStorage),
// le groupe contenant la page active s'ouvre automatiquement.
// =============================================================================

import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { LogOut, User, Zap } from 'lucide-react';

import { useAuth } from '../../contexts/useAuth';
import { USER_ROLES } from '../../types';
import { ResizeHandle } from '../ui';
import { useResizableWidth } from '../../hooks/useResizableWidth';
import GlobalSearch from './GlobalSearch';
import { DASHBOARD_ITEM, isActivePath, navGroupsForUser } from './navConfig';
import SidebarNavGroup, { NavLinkItem } from './SidebarNavGroup';

const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  USER_ROLES.map((r) => [r.value, r.label]),
);

// Etat ouvert/ferme des groupes (par cle). Absent => ouvert par defaut.
const GROUPS_STORAGE_KEY = 'fga.nav.groups';

function readOpenGroups(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(GROUPS_STORAGE_KEY) ?? '{}') as Record<string, boolean>;
  } catch {
    return {};
  }
}

export default function Layout() {
  const location = useLocation();
  const { user, logout } = useAuth();

  // Sidebar de navigation redimensionnable (largeur persistee).
  const { width: navWidth, startResize: startNavResize, isResizing: navResizing } =
    useResizableWidth({ storageKey: 'fga.nav.width', defaultWidth: 256, min: 200, max: 400 });

  const groups = navGroupsForUser(user);

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(readOpenGroups);
  const isOpen = (key: string) => openGroups[key] !== false; // defaut : ouvert
  const toggleGroup = (key: string) =>
    setOpenGroups((prev) => ({ ...prev, [key]: !(prev[key] !== false) }));

  // Persiste l'etat des groupes.
  useEffect(() => {
    try {
      localStorage.setItem(GROUPS_STORAGE_KEY, JSON.stringify(openGroups));
    } catch {
      // localStorage indispo : etat en memoire pour la session.
    }
  }, [openGroups]);

  // Auto-ouvre le groupe contenant la page active (arrivee via recherche/lien).
  useEffect(() => {
    const active = navGroupsForUser(user).find((g) =>
      g.items.some((i) => isActivePath(location.pathname, i.href)),
    );
    if (!active) return;
    // Forme fonctionnelle : `openGroups` n'est pas une dependance -> l'effet ne
    // reagit qu'au changement de ROUTE (le repli manuel du groupe actif reste
    // possible, pas de re-ouverture immediate).
    setOpenGroups((prev) => (prev[active.key] === false ? { ...prev, [active.key]: true } : prev));
  }, [location.pathname, user]);

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar — white, clean, light, redimensionnable */}
      <aside
        style={{ width: navWidth }}
        className="relative shrink-0 bg-white border-r border-slate-200 flex flex-col shadow-sm"
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-6 py-5 border-b border-slate-100">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <Zap className="w-4.5 h-4.5 text-white" />
          </div>
          <span className="text-lg font-bold text-slate-800">FGA CRM</span>
        </div>

        {/* Navigation : Dashboard + groupes depliables */}
        <nav className="px-3 py-4 flex-1 overflow-y-auto">
          <NavLinkItem item={DASHBOARD_ITEM} pathname={location.pathname} />
          <div className="mt-3 space-y-2">
            {groups.map((g) => (
              <SidebarNavGroup
                key={g.key}
                group={g}
                open={isOpen(g.key)}
                onToggle={() => toggleGroup(g.key)}
                pathname={location.pathname}
              />
            ))}
          </div>
        </nav>

        {/* User */}
        <div className="px-3 py-4 border-t border-slate-100">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="w-8 h-8 bg-primary-50 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-primary-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <p className="text-sm font-medium text-slate-700 truncate">{user?.full_name}</p>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-primary-50 text-primary-700">
                  {ROLE_LABELS[user?.role ?? ''] ?? user?.role}
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate">{user?.email}</p>
            </div>
            <button
              onClick={logout}
              className="p-1.5 text-slate-300 hover:text-red-500 transition-colors"
              title="Se déconnecter"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        <ResizeHandle
          onMouseDown={startNavResize}
          isResizing={navResizing}
          label="Redimensionner la navigation"
        />
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header avec recherche globale */}
        <header className="flex items-center justify-end px-8 py-3 bg-white border-b border-slate-200 shadow-sm">
          <GlobalSearch />
        </header>

        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
