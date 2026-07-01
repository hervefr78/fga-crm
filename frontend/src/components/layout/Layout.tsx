// =============================================================================
// FGA CRM - Layout (Light theme, inspired by Startup Radar)
// =============================================================================

import { Link, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Building2,
  Users,
  Target,
  ListTodo,
  Activity,
  Mail,
  FileCheck,
  TrendingUp,
  BarChart3,
  Link2,
  Settings,
  LogOut,
  User,
  Zap,
  Shield,
  Award,
  XCircle,
  Coins,
} from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '../../contexts/useAuth';
import { isAdmin, isManagerOrAbove, USER_ROLES } from '../../types';
import GlobalSearch from './GlobalSearch';

const baseNavigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Contacts', href: '/contacts', icon: Users },
  { name: 'Entreprises', href: '/companies', icon: Building2 },
  { name: 'Pipeline', href: '/pipeline', icon: Target },
  { name: 'Signés', href: '/signed', icon: Award },
  { name: 'Perdus', href: '/lost', icon: XCircle },
  { name: 'Tâches', href: '/tasks', icon: ListTodo },
  { name: 'Activités', href: '/activities', icon: Activity },
  { name: 'Drafts à valider', href: '/drafts', icon: FileCheck },
  { name: 'Email', href: '/email', icon: Mail },
  { name: 'Paramètres', href: '/settings', icon: Settings },
];

const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  USER_ROLES.map((r) => [r.value, r.label]),
);

export default function Layout() {
  const location = useLocation();
  const { user, logout } = useAuth();

  // GEO : module reserve aux managers/admins — masque pour les sales
  // (cf garde RBAC dans GEOPage). Insere juste avant 'Email'.
  const geoNav = isManagerOrAbove(user)
    ? [{ name: 'GEO', href: '/geo', icon: TrendingUp }]
    : [];

  // Trends : signal de demande de marche, reserve managers/admins (garde RBAC
  // dans TrendsPage). Insere juste apres GEO.
  const trendsNav = isManagerOrAbove(user)
    ? [{ name: 'Trends', href: '/trends', icon: BarChart3 }]
    : [];

  // Integrations : op couteuse reservee aux managers/admins (cf garde RBAC
  // backend get_current_manager + ManagerRoute frontend). Masque pour les sales.
  const integrationsNav = isManagerOrAbove(user)
    ? [{ name: 'Integrations', href: '/integrations', icon: Link2 }]
    : [];

  const navigation = [
    ...baseNavigation.slice(0, 9), // jusqu'a 'Drafts à valider' inclus
    ...geoNav,
    ...trendsNav,
    ...baseNavigation.slice(9, 10), // 'Email'
    ...integrationsNav,
    ...baseNavigation.slice(10), // 'Paramètres'
    ...(isAdmin(user)
      ? [
          { name: 'Utilisateurs', href: '/admin/users', icon: Shield },
          { name: 'Conso MCP', href: '/mcp-tokens', icon: Coins },
        ]
      : []),
  ];

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar — white, clean, light */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col shadow-sm">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-6 py-5 border-b border-slate-100">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <Zap className="w-4.5 h-4.5 text-white" />
          </div>
          <span className="text-lg font-bold text-slate-800">FGA CRM</span>
        </div>

        {/* Navigation */}
        <nav className="px-3 py-4 space-y-0.5 flex-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href ||
              (item.href !== '/' && location.pathname.startsWith(item.href));

            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                )}
              >
                <item.icon className={clsx('w-5 h-5', isActive ? 'text-primary-600' : 'text-slate-400')} />
                {item.name}
              </Link>
            );
          })}
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
