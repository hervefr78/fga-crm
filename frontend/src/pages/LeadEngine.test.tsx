// =============================================================================
// FGA CRM - Tests de la page Lead Engine (queue + inbox, api/auth mockes)
// =============================================================================
// Verifie la regle metier dans l'UI : l'outreach (Drafter) n'existe que sur
// mmf_gap ; funding_detected ne propose que l'audit ; inbound_new se qualifie.
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import type { User } from '../types';
import type {
  LeadFunnelResult, LeadQueueResult, LeadSignal, LeadSignalList,
} from '../types/leadEngine';

vi.mock('../api/leadEngine', () => ({
  listLeadSignals: vi.fn(),
  updateLeadSignal: vi.fn(),
  runLeadScan: vi.fn(),
  draftLeadSignal: vi.fn(),
  getLeadQueue: vi.fn(),
  getLeadFunnel: vi.fn(),
}));

// ComposeModal importe api/client (sendEmail, templates, contacts) ;
// qualifyContact est utilise par l'action P3.
vi.mock('../api/client', () => ({
  qualifyContact: vi.fn(),
  sendEmail: vi.fn(),
  getEmailTemplates: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, size: 100 }),
  getContacts: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, size: 200 }),
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

import { qualifyContact } from '../api/client';
import {
  draftLeadSignal, getLeadFunnel, getLeadQueue, listLeadSignals, runLeadScan,
  updateLeadSignal,
} from '../api/leadEngine';
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

const inboundSignal: LeadSignal = {
  id: 's-inb', signal_type: 'inbound_new', status: 'new', company_id: null,
  payload_json: {
    contact_id: 'ct-1', contact_name: 'Léa Martin',
    contact_email: 'lea@beams.fr', lead_source: 'nomo-ia',
  },
  created_at: '2026-07-09T10:00:00Z', updated_at: '2026-07-09T10:00:00Z',
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

const queueResult: LeadQueueResult = {
  items: [
    { signal: mmfSignal, contacts_with_email: 2, has_draft: false },
  ],
  total: 1,
};

const funnelResult: LeadFunnelResult = {
  p1_mmf_gap: { detected: 10, actioned: 4, drafted: 2, sent: 1 },
  p2_funding: { detected: 6, actioned: 3, drafted: 0, sent: 0 },
  p3_inbound: { detected: 1, actioned: 1, drafted: 0, sent: 0 },
  period_days: 30,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><LeadEnginePage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openInbox() {
  fireEvent.click(await screen.findByText('Signal Inbox'));
}

describe('LeadEnginePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.current = admin;
    bulkMock.action = null;
    bulkMock.isRunning = false;
    bulkMock.tasks = [];
    vi.mocked(listLeadSignals).mockResolvedValue(
      list([mmfSignal, fundingSignal, inboundSignal]),
    );
    vi.mocked(updateLeadSignal).mockResolvedValue({ ...mmfSignal, status: 'actioned' });
    vi.mocked(getLeadQueue).mockResolvedValue(queueResult);
    vi.mocked(getLeadFunnel).mockResolvedValue(funnelResult);
  });

  it('bloque l\'acces pour un sales', async () => {
    mockUser.current = sales;
    renderPage();
    expect(await screen.findByText('Accès non autorisé')).toBeInTheDocument();
    expect(listLeadSignals).not.toHaveBeenCalled();
    expect(getLeadQueue).not.toHaveBeenCalled();
  });

  it('vue par defaut : file d\'attente priorisee + funnel', async () => {
    renderPage();
    // Queue : le gap s'affiche en premier (c'est lui qu'on vend)
    expect(await screen.findByText(/Message flou mesuré : audit 24\/75/)).toBeInTheDocument();
    expect(screen.getByText('2 joignables')).toBeInTheDocument();
    expect(screen.getByText('Drafter')).toBeInTheDocument();
    // Funnel visible
    expect(screen.getByText(/Funnel par play/)).toBeInTheDocument();
  });

  it('drafter : genere via outreach-v1 et ouvre la relecture', async () => {
    vi.mocked(draftLeadSignal).mockResolvedValue({
      signal_id: 's-mmf', contact_id: 'ct-9', contact_name: 'Jean CTO',
      contact_email: 'cto@acme.fr', subject: 'Votre message mesure a 24/75',
      body: 'Bonjour…', angle_rationale: 'Gap mesure.',
      generated_at: '2026-07-09T12:00:00Z', meta: { prompt_version: 'outreach-v1' },
    });
    renderPage();
    fireEvent.click(await screen.findByText('Drafter'));
    await waitFor(() => expect(draftLeadSignal).toHaveBeenCalledWith('s-mmf'));
    // Modale de relecture : envoi humain uniquement (jamais automatique)
    expect(await screen.findByText('Draft d\'outreach — à valider')).toBeInTheDocument();
    expect(screen.getByText('Votre message mesure a 24/75')).toBeInTheDocument();
    expect(screen.getByText('Relire et envoyer (composer)')).toBeInTheDocument();
  });

  it('ecarter depuis la queue : signal ignore', async () => {
    renderPage();
    fireEvent.click(await screen.findByText('Écarter'));
    await waitFor(() => {
      expect(updateLeadSignal).toHaveBeenCalledWith('s-mmf', { status: 'ignored' });
    });
  });

  it('inbox : mmf -> decideurs, funding -> audit (jamais d\'outreach direct)', async () => {
    renderPage();
    await openInbox();

    fireEvent.click(await screen.findByText('Chercher les décideurs'));
    expect(bulkMock.startContacts).toHaveBeenCalledWith([
      { id: 'c1', name: 'Acme', startup_radar_id: 'sr-9' },
    ]);
    await waitFor(() => {
      expect(updateLeadSignal).toHaveBeenCalledWith('s-mmf', {
        status: 'actioned', action_kind: 'contacts',
      });
    });

    fireEvent.click(screen.getByText('Auditer le message'));
    expect(bulkMock.startAudit).toHaveBeenCalledWith([
      { id: 'c2', name: 'Sopht', startup_radar_id: 'sr-1' },
    ]);
  });

  it('inbox : inbound -> qualification SPICED (P3)', async () => {
    vi.mocked(qualifyContact).mockResolvedValue({ routing: 'fast_track' });
    renderPage();
    await openInbox();
    fireEvent.click(await screen.findByText('Qualifier (SPICED)'));
    await waitFor(() => expect(qualifyContact).toHaveBeenCalledWith('ct-1'));
    await waitFor(() => {
      expect(updateLeadSignal).toHaveBeenCalledWith('s-inb', {
        status: 'actioned', action_kind: 'qualify',
      });
    });
  });

  it('scan manuel : compte les signaux crees', async () => {
    vi.mocked(runLeadScan).mockResolvedValue({
      created: { funding_detected: 2, mmf_gap: 1, inbound_new: 0 },
    });
    renderPage();
    fireEvent.click(await screen.findByText('Scanner maintenant'));
    expect(await screen.findByText('3 nouveaux signaux')).toBeInTheDocument();
  });
});
