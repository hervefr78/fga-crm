// =============================================================================
// FGA CRM - Tests de la page Trends (api + auth mockes)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { User } from '../types';
import type { TrendCategory, TrendJob, TrendReport } from '../types/trends';

// Mock du module API.
vi.mock('../api/trends', () => ({
  listTrendCategories: vi.fn(),
  createTrendReport: vi.fn(),
  getTrendJob: vi.fn(),
  getTrendReport: vi.fn(),
  getLatestTrendReport: vi.fn(),
  getTrendHealth: vi.fn(),
}));

// Mock de l'auth.
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

import {
  listTrendCategories, createTrendReport, getLatestTrendReport,
  getTrendJob, getTrendReport,
} from '../api/trends';
import TrendsPage from './Trends';

// --- Fixtures ---
const adminUser: User = {
  id: 'u1', email: 'admin@fga.fr', full_name: 'Admin', role: 'admin', is_active: true, avatar_url: null,
};
const managerUser: User = { ...adminUser, role: 'manager' };
const salesUser: User = { ...adminUser, role: 'sales' };

const category: TrendCategory = {
  id: 'c1', slug: 'marketing-digital', label: 'Marketing Digital', provider: 'mock',
  provider_category_id: '2', parent_slug: null, active: true, display_order: 0,
};

const report: TrendReport = {
  job_id: 'j1',
  status: 'completed',
  summary_md: '# Tendances',
  opportunity_score: 74.3,
  signals: {
    market_pulse: { interest_index: 62.5, direction: 'up', freshness: 'fresh' },
    timeseries: [{ date: '2026-05-01', value: 60 }, { date: '2026-05-08', value: 65 }],
    rising_queries: [
      { query: 'prospection ia', value: 90, growth: 320, breakout: false },
      { query: 'sales automation', value: 80, growth: 5000, breakout: true },
    ],
    top_queries: [{ query: 'crm', value: 100, growth: null, breakout: false }],
    related_topics: [],
    regions: [{ region: 'Ile-de-France', value: 88 }],
  },
  meta: {
    provider_effective: 'mock', generated_at: '2026-06-01T00:00:00Z', cached: false,
    category_slug: 'marketing-digital', country: 'FR', language: 'fr', timeframe: 'today 12-m',
  },
};

const completedJob: TrendJob = {
  job_id: 'j1', mode: 'quick', status: 'completed', provider_primary: 'mock',
  provider_effective: 'mock', cache_hit: false, started_at: null, finished_at: null,
  error: null, progress: { steps_total: 4, steps_done: 4 }, created_at: '2026-06-01T00:00:00Z',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <TrendsPage />
    </QueryClientProvider>,
  );
}

describe('TrendsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.current = adminUser;
    vi.mocked(listTrendCategories).mockResolvedValue([category]);
    vi.mocked(getLatestTrendReport).mockRejectedValue(new Error('404'));
  });

  it('bloque l\'acces pour un sales', async () => {
    mockUser.current = salesUser;
    renderPage();
    expect(await screen.findByText('Acces non autorise')).toBeInTheDocument();
    expect(listTrendCategories).not.toHaveBeenCalled();
  });

  it('affiche le titre et le bandeau de filtres pour un manager', async () => {
    mockUser.current = managerUser;
    renderPage();
    expect(await screen.findByText('Trends — Signal de marche')).toBeInTheDocument();
    expect(screen.getByText("Lancer l'analyse")).toBeInTheDocument();
  });

  it('affiche un etat vide quand aucun rapport', async () => {
    renderPage();
    expect(
      await screen.findByText(/Choisissez une categorie et lancez une analyse/),
    ).toBeInTheDocument();
  });

  it('affiche le rapport (KPI + rising) quand un dernier rapport existe', async () => {
    vi.mocked(getLatestTrendReport).mockResolvedValue(report);
    renderPage();
    // Score d'opportunite
    expect(await screen.findByText('74.3')).toBeInTheDocument();
    // Indice d'interet
    expect(screen.getByText('62.5')).toBeInTheDocument();
    // Requete rising + badge breakout
    expect(screen.getByText('sales automation')).toBeInTheDocument();
    expect(screen.getByText('breakout')).toBeInTheDocument();
  });

  it('lance une analyse au clic sur le bouton', async () => {
    vi.mocked(createTrendReport).mockResolvedValue(completedJob);
    renderPage();
    // Attendre le chargement des categories (sinon le bouton reste desactive).
    await screen.findByText('Marketing Digital');
    const btn = await screen.findByText("Lancer l'analyse");
    fireEvent.click(btn);
    await waitFor(() => {
      expect(createTrendReport).toHaveBeenCalledWith(
        expect.objectContaining({ mode: 'quick', category_id: 'c1' }),
      );
    });
  });

  it('affiche le feedback "en cours" des le clic, pendant le POST (avant creation du job)', async () => {
    // POST volontairement non resolu : on observe l'etat "occupe" pendant l'appel,
    // AVANT meme que le job existe (activeJobId encore null). C'est la fenetre qui
    // ne montrait qu'un bouton grise.
    vi.mocked(createTrendReport).mockReturnValue(new Promise<TrendJob>(() => {}));
    renderPage();
    await screen.findByText('Marketing Digital');
    fireEvent.click(screen.getByText("Lancer l'analyse"));

    // Bouton en chargement (label change) + carte d'etat visible.
    expect(await screen.findByText(/Analyse en cours/)).toBeInTheDocument();
    expect(screen.getByText(/Le rapport s.affichera automatiquement/)).toBeInTheDocument();
    // Le bouton est desactive et l'etat vide a disparu.
    expect(screen.getByRole('button', { name: /Analyse en cours/ })).toBeDisabled();
    expect(screen.queryByText(/Choisissez une categorie/)).not.toBeInTheDocument();
  });

  it('maintient le feedback tant que le job tourne (polling)', async () => {
    vi.mocked(createTrendReport).mockResolvedValue({ ...completedJob, status: 'running' });
    vi.mocked(getTrendJob).mockResolvedValue({ ...completedJob, status: 'running' });
    renderPage();
    await screen.findByText('Marketing Digital');
    fireEvent.click(screen.getByText("Lancer l'analyse"));

    // La carte "en cours" reste affichee pendant que le job est running.
    expect(await screen.findByText(/Le rapport s.affichera automatiquement/)).toBeInTheDocument();
    expect(screen.getByText(/Analyse en cours/)).toBeInTheDocument();
  });

  it('masque le feedback et affiche le rapport une fois le job complete', async () => {
    vi.mocked(createTrendReport).mockResolvedValue(completedJob);
    vi.mocked(getTrendJob).mockResolvedValue(completedJob);
    vi.mocked(getTrendReport).mockResolvedValue(report);
    renderPage();
    await screen.findByText('Marketing Digital');
    fireEvent.click(screen.getByText("Lancer l'analyse"));

    // Le rapport s'affiche (score) et le feedback "en cours" a disparu (pas de
    // flash d'etat vide ni de "en cours" bloque).
    expect(await screen.findByText('74.3')).toBeInTheDocument();
    expect(screen.queryByText(/Analyse en cours/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Le rapport s.affichera automatiquement/)).not.toBeInTheDocument();
  });
});
