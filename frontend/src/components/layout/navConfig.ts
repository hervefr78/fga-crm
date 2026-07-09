// =============================================================================
// FGA CRM - Navigation : configuration des groupes de la sidebar
// =============================================================================
// Source unique de la structure de navigation (DC8) :
//   Dashboard (hors groupe) puis 3 groupes depliables — Sales / Marketing /
//   Reglages. Chaque item peut etre restreint par role (`access`) ; un groupe
//   sans item visible est masque entierement (ex: profil sales sans acces GEO).
// =============================================================================

import type { ElementType } from 'react';
import {
  LayoutDashboard,
  Building2, Users, Target, Award, XCircle, ListTodo, Activity,
  RadioTower, TrendingUp, BarChart3, UserPlus, Mail, FileCheck,
  Settings, Link2, Shield, Coins,
} from 'lucide-react';

import type { User } from '../../types';
import { isAdmin, isManagerOrAbove } from '../../types';

export interface NavItem {
  name: string;
  href: string;
  icon: ElementType;
  // Restriction d'acces (refletee par les gardes RBAC des pages/backend).
  access?: 'manager' | 'admin';
}

export interface NavGroup {
  key: string;
  label: string;
  items: NavItem[];
}

// Point d'entree : toujours visible, hors groupe.
export const DASHBOARD_ITEM: NavItem = { name: 'Dashboard', href: '/', icon: LayoutDashboard };

const GROUPS: NavGroup[] = [
  {
    key: 'sales',
    label: 'Sales',
    items: [
      { name: 'Entreprises', href: '/companies', icon: Building2 },
      { name: 'Contacts', href: '/contacts', icon: Users },
      { name: 'Pipeline', href: '/pipeline', icon: Target },
      { name: 'Signés', href: '/signed', icon: Award },
      { name: 'Perdus', href: '/lost', icon: XCircle },
      { name: 'Tâches', href: '/tasks', icon: ListTodo },
      { name: 'Activités', href: '/activities', icon: Activity },
    ],
  },
  {
    key: 'marketing',
    label: 'Marketing',
    items: [
      { name: 'Lead Engine', href: '/lead-engine', icon: RadioTower, access: 'manager' },
      { name: 'GEO', href: '/geo', icon: TrendingUp, access: 'manager' },
      { name: 'Trends', href: '/trends', icon: BarChart3, access: 'manager' },
      { name: 'Enrichissement', href: '/enrichment', icon: UserPlus, access: 'manager' },
      { name: 'Email', href: '/email', icon: Mail },
      { name: 'Drafts à valider', href: '/drafts', icon: FileCheck },
    ],
  },
  {
    key: 'settings',
    label: 'Réglages',
    items: [
      { name: 'Paramètres', href: '/settings', icon: Settings },
      { name: 'Integrations', href: '/integrations', icon: Link2, access: 'manager' },
      { name: 'Utilisateurs', href: '/admin/users', icon: Shield, access: 'admin' },
      { name: 'Conso MCP', href: '/mcp-tokens', icon: Coins, access: 'admin' },
    ],
  },
];

function canSee(user: User | null, access?: NavItem['access']): boolean {
  if (access === 'admin') return isAdmin(user);
  if (access === 'manager') return isManagerOrAbove(user);
  return true;
}

/** Groupes visibles pour un utilisateur : items filtres par role, groupes vides retires. */
export function navGroupsForUser(user: User | null): NavGroup[] {
  return GROUPS
    .map((g) => ({ ...g, items: g.items.filter((i) => canSee(user, i.access)) }))
    .filter((g) => g.items.length > 0);
}

/** Une route est active si elle correspond au href (prefixe, sauf racine). */
export function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || (href !== '/' && pathname.startsWith(href));
}
