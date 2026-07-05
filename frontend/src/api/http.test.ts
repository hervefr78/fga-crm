// =============================================================================
// FGA CRM - Tests du garde anti-boucle 401 (http.ts)
// =============================================================================
// Regression : login qui clignote a l'infini. Cause = intercepteur 401 qui fait
// window.location.href = '/login' meme quand on est DEJA sur /login, combine a la
// sonde getMe() du boot (AuthContext, sans token) -> 401 -> reload -> boucle.

import { describe, it, expect } from 'vitest';
import { shouldForceLoginRedirect } from './http';

describe('shouldForceLoginRedirect', () => {
  it('NE redirige PAS sur un 401 quand on est deja sur /login (anti-boucle)', () => {
    // Le cas du bug : sonde getMe() sans token sur la page de login.
    expect(shouldForceLoginRedirect(401, null, '/login')).toBe(false);
    expect(shouldForceLoginRedirect(401, 'un-token-expire', '/login')).toBe(false);
  });

  it('redirige sur un 401 en cours d\'app (session expiree hors /login)', () => {
    expect(shouldForceLoginRedirect(401, 'un-token', '/dashboard')).toBe(true);
    expect(shouldForceLoginRedirect(401, null, '/companies/123')).toBe(true);
  });

  it('NE redirige PAS en mode dev-bypass', () => {
    expect(shouldForceLoginRedirect(401, 'dev-bypass', '/dashboard')).toBe(false);
  });

  it('NE redirige PAS sur un statut != 401', () => {
    expect(shouldForceLoginRedirect(500, 'un-token', '/dashboard')).toBe(false);
    expect(shouldForceLoginRedirect(undefined, 'un-token', '/dashboard')).toBe(false);
    expect(shouldForceLoginRedirect(403, 'un-token', '/dashboard')).toBe(false);
  });
});
