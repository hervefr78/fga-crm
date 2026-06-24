// =============================================================================
// FGA CRM - Tests page Integrations (full sync SR via polling de statut)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { SyncStatus } from '../types';

// Mock du module API : on controle le statut sans toucher au reseau.
vi.mock('../api/client', () => ({
  syncStartupRadar: vi.fn(),
  getSyncStatus: vi.fn(),
}));

import { getSyncStatus } from '../api/client';
import IntegrationsPage from './Integrations';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <IntegrationsPage />
    </QueryClientProvider>,
  );
}

function makeStatus(overrides: Partial<SyncStatus>): SyncStatus {
  return {
    has_synced: false,
    status: 'idle',
    started_at: null,
    finished_at: null,
    error: null,
    last_result: null,
    ...overrides,
  };
}

describe('IntegrationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('affiche le resultat quand la derniere sync est completed', async () => {
    vi.mocked(getSyncStatus).mockResolvedValue(
      makeStatus({
        has_synced: true,
        status: 'completed',
        finished_at: '2026-06-24T10:05:00+00:00',
        last_result: {
          companies_created: 12,
          companies_updated: 0,
          contacts_created: 4,
          contacts_updated: 0,
          investors_created: 0,
          investors_updated: 0,
          audits_created: 0,
          errors: [],
        },
      }),
    );

    renderPage();

    // Les compteurs des StatCards sont des noeuds texte fiables ("+12", "+4")
    await waitFor(() => expect(screen.getByText('+12')).toBeInTheDocument());
    expect(screen.getByText('+4')).toBeInTheDocument();
  });

  it('affiche "en cours" quand une sync tourne (status=running)', async () => {
    vi.mocked(getSyncStatus).mockResolvedValue(
      makeStatus({ status: 'running', started_at: '2026-06-24T10:00:00+00:00' }),
    );

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/Synchronisation en cours/i)).toBeInTheDocument(),
    );
    // Le bouton est desactive pendant la sync
    expect(screen.getByRole('button', { name: /Synchronisation/i })).toBeDisabled();
  });

  it('affiche l\'erreur quand la derniere sync a echoue (status=failed)', async () => {
    vi.mocked(getSyncStatus).mockResolvedValue(
      makeStatus({
        status: 'failed',
        finished_at: '2026-06-24T10:01:00+00:00',
        error: 'SR injoignable',
      }),
    );

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/a echoue/i)).toBeInTheDocument(),
    );
    expect(screen.getByText('SR injoignable')).toBeInTheDocument();
  });
});
