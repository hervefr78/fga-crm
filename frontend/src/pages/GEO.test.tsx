// =============================================================================
// FGA CRM - Tests de la page GEO (api + auth mockes)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { User } from '../types';
import type {
  GeoBrand, GeoDashboard, GeoGap, GeoPrompt,
} from '../types/geo';

// Mock du module API : on controle les reponses sans toucher au reseau.
vi.mock('../api/geo', () => ({
  listGeoBrands: vi.fn(),
  getGeoDashboard: vi.fn(),
  getGeoGaps: vi.fn(),
  getGeoAlerts: vi.fn(),
  getGeoHealth: vi.fn(),
  listGeoPrompts: vi.fn(),
  triggerGeoRun: vi.fn(),
  triggerGeoRemeasure: vi.fn(),
  createGeoBrand: vi.fn(),
  createGeoPrompt: vi.fn(),
  deleteGeoPrompt: vi.fn(),
}));

// Mock de l'auth : on injecte un user dont on controle le role par test.
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
  listGeoBrands, getGeoDashboard, getGeoGaps, getGeoAlerts,
  getGeoHealth, listGeoPrompts, triggerGeoRemeasure, createGeoBrand,
} from '../api/geo';
import GEOPage from './GEO';

// --- Fixtures ---
const adminUser: User = {
  id: 'u1', email: 'admin@fga.fr', full_name: 'Admin', role: 'admin', is_active: true, avatar_url: null,
};
const managerUser: User = { ...adminUser, role: 'manager' };
const salesUser: User = { ...adminUser, role: 'sales' };

const brand: GeoBrand = {
  id: 'b1', slug: 'fga', name: 'Fast Growth', aliases: [], is_owned: true, active: true,
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

const dashboard: GeoDashboard = {
  brand,
  engine: 'perplexity',
  date_from: '2026-05-01',
  date_to: '2026-06-01',
  metrics: [
    {
      id: 'm1', day: '2026-05-15', brand_id: 'b1', engine: 'perplexity',
      visibility_rate: 60, sov: 25, sov_weighted: 30, sentiment_avg: 0.5,
      reco_rate: 0.4, runs_total: 10, computed_at: '2026-05-15T00:00:00Z',
    },
  ],
  top_competitors: [{ nom: 'Concurrent A', mentions: 5, sov_share: 40 }],
  top_sources: [{ domain: 'example.com', count: 3 }],
};

const gap: GeoGap = {
  prompt_id: 'p1',
  prompt_text: 'Quel est le meilleur cabinet de conseil en croissance ?',
  intent: 'comparatif',
  priority: true,
  runs_checked: 3,
  mentions: 0,
  visibility_rate: 0,
  top_competitor_sources: [],
  top_competitors: [],
  last_run_at: null,
  action_suggestion: 'Publier une comparaison structuree sur le site',
};

const prompt: GeoPrompt = {
  id: 'p1', brand_id: 'b1', text: 'prompt', intent: 'comparatif', persona: null,
  country: 'FR', language: 'fr', tags: [], priority: true, active: true,
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <GEOPage />
    </QueryClientProvider>,
  );
}

function mockHappyPath() {
  vi.mocked(listGeoBrands).mockResolvedValue([brand]);
  vi.mocked(getGeoDashboard).mockResolvedValue(dashboard);
  vi.mocked(getGeoGaps).mockResolvedValue([gap]);
  vi.mocked(getGeoAlerts).mockResolvedValue([]);
  vi.mocked(getGeoHealth).mockResolvedValue([
    { engine: 'perplexity', status: 'ok', checked_at: '2026-06-01T00:00:00Z', error: null },
  ]);
  vi.mocked(listGeoPrompts).mockResolvedValue([prompt]);
}

describe('GEOPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.current = adminUser;
  });

  it('bloque l\'acces pour un sales', async () => {
    mockUser.current = salesUser;
    renderPage();
    expect(await screen.findByText('Acces non autorise')).toBeInTheDocument();
    expect(listGeoBrands).not.toHaveBeenCalled();
  });

  it('affiche le dashboard et les KPI pour un admin', async () => {
    mockHappyPath();
    renderPage();

    expect(await screen.findByText('GEO — Visibilite IA')).toBeInTheDocument();
    // KPI Visibilite : moyenne = 60 -> "60.0 %"
    expect(await screen.findByText('60.0 %')).toBeInTheDocument();
    // Sentiment positif (0.5 > 0.2)
    expect(screen.getByText('Positif')).toBeInTheDocument();
    // Top source
    expect(screen.getByText('example.com')).toBeInTheDocument();
  });

  it('affiche un etat vide quand aucune marque', async () => {
    vi.mocked(listGeoBrands).mockResolvedValue([]);
    renderPage();
    expect(
      await screen.findByText(/Aucune marque configuree/),
    ).toBeInTheDocument();
  });

  it('permet a un admin d\'ajouter une marque depuis l\'etat vide', async () => {
    vi.mocked(listGeoBrands).mockResolvedValue([]);
    vi.mocked(createGeoBrand).mockResolvedValue(brand);
    renderPage();

    // L'admin voit le bouton d'ajout dans l'etat vide.
    const addBtn = await screen.findByText('Ajouter une marque');
    fireEvent.click(addBtn);

    // La modale s'ouvre : on saisit le nom + on cree.
    const input = await screen.findByPlaceholderText(/Fast Growth Advisor/);
    fireEvent.change(input, { target: { value: 'Ma Marque' } });
    fireEvent.click(screen.getByText('Creer'));

    await waitFor(() => {
      expect(createGeoBrand).toHaveBeenCalledWith({
        name: 'Ma Marque',
        slug: 'ma-marque',
        aliases: [],
        is_owned: true,
      });
    });
  });

  it('affiche les gaps et declenche la re-mesure (admin)', async () => {
    mockHappyPath();
    vi.mocked(triggerGeoRemeasure).mockResolvedValue({ task_id: 't1', runs_scheduled: 3 });

    renderPage();

    const btn = await screen.findByText('Declencher re-mesure');
    fireEvent.click(btn);

    await waitFor(() => {
      expect(triggerGeoRemeasure).toHaveBeenCalled();
    });
    // Message de succes avec task_id et nombre de runs
    expect(await screen.findByText(/Re-mesure planifiee : 3 mesure/)).toBeInTheDocument();
  });

  it('masque les actions d\'ecriture pour un manager (pas de bouton run)', async () => {
    mockUser.current = managerUser;
    mockHappyPath();
    vi.mocked(getGeoHealth).mockResolvedValue([]); // managers : pas de health

    renderPage();

    await screen.findByText('GEO — Visibilite IA');
    expect(screen.queryByText('Lancer un run')).not.toBeInTheDocument();
    expect(screen.queryByText('Declencher re-mesure')).not.toBeInTheDocument();
  });
});
