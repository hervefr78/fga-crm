// =============================================================================
// FGA CRM - Tests navConfig (groupes de navigation filtres par role)
// =============================================================================

import { describe, it, expect } from 'vitest';

import type { User } from '../../types';
import { navGroupsForUser, isActivePath } from './navConfig';

const asUser = (role: string): User =>
  ({ id: 'u1', email: 'u@fga.fr', full_name: 'U', role, is_active: true, avatar_url: null } as User);

const names = (groups: ReturnType<typeof navGroupsForUser>, key: string) =>
  groups.find((g) => g.key === key)?.items.map((i) => i.name) ?? [];

describe('navGroupsForUser', () => {
  it('admin : voit tout (3 groupes complets)', () => {
    const groups = navGroupsForUser(asUser('admin'));
    expect(groups.map((g) => g.key)).toEqual(['sales', 'marketing', 'settings']);
    expect(names(groups, 'marketing')).toEqual(['GEO', 'Trends', 'Enrichissement', 'Email', 'Drafts à valider']);
    expect(names(groups, 'settings')).toEqual(['Paramètres', 'Integrations', 'Utilisateurs', 'Conso MCP']);
  });

  it('manager : pas d entrees admin (Utilisateurs, Conso MCP)', () => {
    const groups = navGroupsForUser(asUser('manager'));
    expect(names(groups, 'settings')).toEqual(['Paramètres', 'Integrations']);
    expect(names(groups, 'marketing')).toContain('GEO');
  });

  it('sales : Marketing reduit a Email + Drafts, Reglages reduit a Parametres', () => {
    const groups = navGroupsForUser(asUser('sales'));
    expect(names(groups, 'marketing')).toEqual(['Email', 'Drafts à valider']);
    expect(names(groups, 'settings')).toEqual(['Paramètres']);
    // Sales complet dans tous les cas
    expect(names(groups, 'sales')).toEqual([
      'Entreprises', 'Contacts', 'Pipeline', 'Signés', 'Perdus', 'Tâches', 'Activités',
    ]);
  });

  it('groupe entierement vide -> retire', () => {
    // Aucun groupe actuel ne devient vide, mais le contrat est garanti :
    // tous les groupes retournes ont au moins un item.
    for (const role of ['admin', 'manager', 'sales']) {
      for (const g of navGroupsForUser(asUser(role))) {
        expect(g.items.length).toBeGreaterThan(0);
      }
    }
  });
});

describe('isActivePath', () => {
  it('racine : exacte uniquement', () => {
    expect(isActivePath('/', '/')).toBe(true);
    expect(isActivePath('/companies', '/')).toBe(false);
  });

  it('routes : prefixe (detail actif sur la section)', () => {
    expect(isActivePath('/companies/123', '/companies')).toBe(true);
    expect(isActivePath('/contacts', '/companies')).toBe(false);
  });
});
