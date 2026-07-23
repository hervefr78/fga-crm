// =============================================================================
// FGA CRM - Tests de la page Radar & Calendrier (FGA Pulse)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { User } from '../types';

// Mock de l'API Pulse (service autonome) : on controle /health sans reseau.
vi.mock('../api/pulse', () => ({
  getPulseHealth: vi.fn(),
}));

// Mock de l'auth : role controle par test.
const mockUser: { current: User | null } = { current: null };
vi.mock('../contexts/useAuth', () => ({
  useAuth: () => ({
    user: mockUser.current,
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

import { getPulseHealth } from '../api/pulse';
import PulsePage from './Pulse';

const adminUser: User = {
  id: 'u1', email: 'admin@fga.fr', full_name: 'Admin', role: 'admin', is_active: true, avatar_url: null,
};
const salesUser: User = { ...adminUser, role: 'sales' };

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <PulsePage />
    </QueryClientProvider>,
  );
}

describe('PulsePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.current = adminUser;
  });

  it('bloque l\'acces pour un sales', async () => {
    mockUser.current = salesUser;
    renderPage();
    expect(await screen.findByText('Accès non autorisé')).toBeInTheDocument();
    expect(getPulseHealth).not.toHaveBeenCalled();
  });

  it('affiche le titre et l\'etat vide pour un admin, service en ligne', async () => {
    vi.mocked(getPulseHealth).mockResolvedValue({ status: 'ok', db: 'ok', redis: 'ok' });
    renderPage();
    expect(await screen.findByText('Radar & Calendrier')).toBeInTheDocument();
    expect(await screen.findByText('Service en ligne')).toBeInTheDocument();
    expect(screen.getByText(/arrivent aux prochains sprints/)).toBeInTheDocument();
  });

  it('affiche l\'etat degrade quand le service signale un composant down', async () => {
    vi.mocked(getPulseHealth).mockResolvedValue({ status: 'degraded', db: 'down', redis: 'ok' });
    renderPage();
    expect(await screen.findByText(/Dégradé/)).toBeInTheDocument();
  });

  it('affiche injoignable quand /health echoue', async () => {
    vi.mocked(getPulseHealth).mockRejectedValue(new Error('network'));
    renderPage();
    expect(await screen.findByText('Service injoignable')).toBeInTheDocument();
  });
});
