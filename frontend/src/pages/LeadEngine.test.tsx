// =============================================================================
// FGA CRM - Tests de la page Lead Engine / Signal Inbox (api + auth mockes)
// =============================================================================
// Verifie la regle metier dans l'UI : mmf_gap -> "Chercher les décideurs"
// (outreach), funding_detected -> "Auditer le message" (jamais d'outreach).
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import type { User } from '../types';
import type { LeadSignal, LeadSignalList } from '../types/leadEngine';

vi.mock('../api/leadEngine', () => ({
  listLeadSignals: vi.fn(),
  updateLeadSignal: vi.fn(),
  runLeadScan: vi.fn(),
}));

const mockUser: { current: User | null } = { current: null };
vi.mock('../contexts/useAuth', () => ({
  useAuth: () => ({
    user: mockUser.current, isAuthenticated: true, isLoading: false,
    login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(),
  }),
}));

// Bulk action mocke : pas de polling reel dans les tests de page.
const bulkMock = {
  action: null as string | null,
  tasks: [] as unknown[],
  summary: { total: 0, running: 0, done: 0, failed: 0, skipped: 0 },
  isRunning: false,
  startAudit: vi.fn(),
  startContacts: vi.fn(),
  reset: vi.fn(),
};
vi.mock('../components/companies/useCompanyBulkAction', () => ({
  useCompanyBulkAction: () => bulkMock,
}));

import { listLeadSignals, updateLeadSignal, runLeadScan } from '../api/leadEngine';
import LeadEnginePage from './LeadEngine';

const admin: User = {
  id: 'u1', email: 'a@fga.fr', full_name: 'A', role: 'admin', is_active: true, avatar_url: null,
};
const sales: User = { ...admin, role: 'sales' };

const mmfSignal: LeadSignal = {
  id: 's-mmf', signal_type: 'mmf_gap', status: 'new', company_id: 'c1',
  payload_json: {
    company_name: 'Acme', startup_radar_id: 'sr-9', audit_score: 24,
    funding_amount: 2_000_000, funding_series: 'Seed', funding_date: '2026-07-01',
  },
  created_at: '2026-07-09T08:00:00Z', updated_at: '2026-07-09T08:00:00Z',
};

const fundingSignal: LeadSignal = {
  id: 's-fund', signal_type: 'funding_detected', status: 'new', company_id: 'c2',
  payload_json: {
    company_name: 'Sopht', startup_radar_id: 'sr-1',
    funding_amount: 4_500_000, funding_series: 'Série A', funding_date: '2026-06-27',
  },
  created_at: '2026-07-09T09:00:00Z', updated_at: '2026-07-09T09:00:00Z',
};

function list(items: LeadSignal[]): LeadSignalList {
  return {
    items, total: items.length, page: 1, size: 20,
    stats: {
      new_total: items.length,
      new_funding: items.filter((s) => s.signal_type === 'funding_detected').length,
      new_mmf: items.filter((s) => s.signal_type === 'mmf_gap').length,
      actioned_7d: 3, ignored_7d: 1,
    },
  };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><LeadEnginePage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('LeadEnginePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.current = admin;
    bulkMock.action = null;
    bulkMock.isRunning = false;
    bulkMock.tasks = [];
    vi.mocked(listLeadSignals).mockResolvedValue(list([mmfSignal, fundingSignal]));
    vi.mocked(updateLeadSignal).mockResolvedValue({ ...mmfSignal, status: 'actioned' });
  });

  it('bloque l\'acces pour un sales', async () => {
    mockUser.current = sales;
    renderPage();
    expect(await screen.findByText('Accès non autorisé')).toBeInTheDocument();
    expect(listLeadSignals).not.toHaveBeenCalled();
  });

  it('affiche l\'inbox : raison du gap en premier, solvabilite en qualificateur', async () => {
    renderPage();
    expect(await screen.findByText('Acme')).toBeInTheDocument();
    // Le gap (ce qu'on vend) est la raison affichee du signal mmf.
    expect(screen.getByText(/Message flou mesuré : audit 24\/75/)).toBeInTheDocument();
    // KPI depuis les stats backend.
    expect(screen.getByText('Traités (7 j)')).toBeInTheDocument();
  });

  it('mmf_gap -> recherche de decideurs + transition actioned', async () => {
    renderPage();
    fireEvent.click(await screen.findByText('Chercher les décideurs'));
    expect(bulkMock.startContacts).toHaveBeenCalledWith([
      { id: 'c1', name: 'Acme', startup_radar_id: 'sr-9' },
    ]);
    await waitFor(() => {
      expect(updateLeadSignal).toHaveBeenCalledWith('s-mmf', {
        status: 'actioned', action_kind: 'contacts',
      });
    });
  });

  it('funding_detected -> audit du message (jamais d\'outreach direct)', async () => {
    renderPage();
    fireEvent.click(await screen.findByText('Auditer le message'));
    expect(bulkMock.startAudit).toHaveBeenCalledWith([
      { id: 'c2', name: 'Sopht', startup_radar_id: 'sr-1' },
    ]);
    expect(bulkMock.startContacts).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(updateLeadSignal).toHaveBeenCalledWith('s-fund', {
        status: 'actioned', action_kind: 'audit',
      });
    });
  });

  it('ignorer un signal', async () => {
    renderPage();
    fireEvent.click((await screen.findAllByText('Ignorer'))[0]);
    await waitFor(() => {
      expect(updateLeadSignal).toHaveBeenCalledWith('s-mmf', { status: 'ignored' });
    });
  });

  it('scan manuel : compte les signaux crees', async () => {
    vi.mocked(runLeadScan).mockResolvedValue({ created: { funding_detected: 2, mmf_gap: 1 } });
    renderPage();
    fireEvent.click(await screen.findByText('Scanner maintenant'));
    expect(await screen.findByText('3 nouveaux signaux')).toBeInTheDocument();
  });
});
