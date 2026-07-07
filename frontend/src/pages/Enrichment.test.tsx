// =============================================================================
// FGA CRM - Tests de la page Enrichissement (api + auth mockes)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { User } from '../types';
import type { EnrichmentJob } from '../types/enrichment';

vi.mock('../api/enrichment', () => ({
  listEnrichmentJobs: vi.fn(),
  createEnrichmentJob: vi.fn(),
  getEnrichmentJob: vi.fn(),
}));

const mockUser: { current: User | null } = { current: null };
vi.mock('../contexts/useAuth', () => ({
  useAuth: () => ({
    user: mockUser.current, isAuthenticated: true, isLoading: false,
    login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(),
  }),
}));

import { listEnrichmentJobs, createEnrichmentJob } from '../api/enrichment';
import EnrichmentPage from './Enrichment';

const admin: User = {
  id: 'u1', email: 'a@fga.fr', full_name: 'A', role: 'admin', is_active: true, avatar_url: null,
};
const manager: User = { ...admin, role: 'manager' };
const sales: User = { ...admin, role: 'sales' };

const job: EnrichmentJob = {
  id: 'j1', mode: 'company', status: 'done',
  stats_json: { companies: 1, people_found: 3, emails_found: 2, valid: 2, credits_spent: 5 },
  error: null, created_at: '2026-07-02T10:00:00Z', finished_at: '2026-07-02T10:01:00Z',
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><EnrichmentPage /></QueryClientProvider>,
  );
}

describe('EnrichmentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.current = admin;
    vi.mocked(listEnrichmentJobs).mockResolvedValue({ items: [], total: 0, page: 1, size: 20 });
  });

  it('bloque l\'acces pour un sales', async () => {
    mockUser.current = sales;
    renderPage();
    expect(await screen.findByText('Acces non autorise')).toBeInTheDocument();
    expect(listEnrichmentJobs).not.toHaveBeenCalled();
  });

  it('affiche la page pour un manager', async () => {
    mockUser.current = manager;
    renderPage();
    expect(await screen.findByText('Enrichissement')).toBeInTheDocument();
    expect(screen.getByText('Lancer l’enrichissement')).toBeInTheDocument();
  });

  it('affiche les jobs existants', async () => {
    vi.mocked(listEnrichmentJobs).mockResolvedValue({ items: [job], total: 1, page: 1, size: 20 });
    renderPage();
    expect(await screen.findByText('Termine')).toBeInTheDocument();
  });

  it('lance un enrichissement a la demande (mode company)', async () => {
    vi.mocked(createEnrichmentJob).mockResolvedValue(job);
    renderPage();
    const input = await screen.findByPlaceholderText('123456789');
    fireEvent.change(input, { target: { value: '123456789' } });
    fireEvent.click(screen.getByText('Lancer l’enrichissement'));
    await waitFor(() => {
      expect(createEnrichmentJob).toHaveBeenCalledWith(
        expect.objectContaining({ mode: 'company', siren: '123456789' }),
      );
    });
  });

  it('lance un enrichissement par provenance (mode source)', async () => {
    vi.mocked(createEnrichmentJob).mockResolvedValue(job);
    renderPage();
    // Bascule sur le mode Par provenance, choisit Nomo-IA, lance.
    fireEvent.click(await screen.findByText('Par provenance'));
    fireEvent.change(screen.getByDisplayValue('Startup Radar'), {
      target: { value: 'nomo-ia' },
    });
    fireEvent.click(screen.getByText('Lancer l’enrichissement'));
    await waitFor(() => {
      expect(createEnrichmentJob).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: 'source',
          source_filter: { lead_source: 'nomo-ia', limit: 200 },
        }),
      );
    });
  });
});
