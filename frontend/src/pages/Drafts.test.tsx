// =============================================================================
// FGA CRM - Tests de la page Drafts à valider (api mocké)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { DraftReview } from '../types';

// Mock du module API : on controle les reponses sans toucher au reseau.
vi.mock('../api/drafts', () => ({
  listPendingDrafts: vi.fn(),
  updateDraftStatus: vi.fn(),
  exportHeyReachCsv: vi.fn(),
}));

import { listPendingDrafts, updateDraftStatus, exportHeyReachCsv } from '../api/drafts';
import DraftsPage from './Drafts';

const sampleDraft: DraftReview = {
  draft_id: 'd1',
  lead_id: 'lead-1',
  type: 'linkedin_dm',
  content: 'Bonjour, ravi de vous contacter.',
  status: 'to-review',
  brand: 'fga',
  sequence_day: null,
  voice_pack_used: 'fga_voice',
  voice_check_passed: true,
  published_url: null,
  created_by: 'mcp',
  created_at: '2026-06-23T10:00:00Z',
  metadata: null,
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DraftsPage />
    </QueryClientProvider>,
  );
}

describe('DraftsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('affiche les drafts retournés par l\'API', async () => {
    vi.mocked(listPendingDrafts).mockResolvedValue([sampleDraft]);

    renderPage();

    expect(await screen.findByText('Message LinkedIn')).toBeInTheDocument();
    // 'FGA' apparait deux fois (onglet de filtre + badge marque) : on cible le badge.
    const fgaMatches = screen.getAllByText('FGA');
    expect(fgaMatches.length).toBeGreaterThanOrEqual(1);
    expect(fgaMatches.some((el) => el.tagName.toLowerCase() === 'span')).toBe(true);
    expect(screen.getByText('voix ✓')).toBeInTheDocument();
    expect(screen.getByText('Approuver')).toBeInTheDocument();
    expect(screen.getByText('Rejeter')).toBeInTheDocument();
  });

  it('affiche un état vide quand aucune donnée', async () => {
    vi.mocked(listPendingDrafts).mockResolvedValue([]);

    renderPage();

    expect(
      await screen.findByText('Aucun draft en attente de validation'),
    ).toBeInTheDocument();
  });

  it('affiche un état d\'erreur sans écran blanc', async () => {
    vi.mocked(listPendingDrafts).mockRejectedValue(new Error('boom'));

    renderPage();

    expect(await screen.findByText('Réessayer')).toBeInTheDocument();
  });

  it('appelle updateDraftStatus avec "approved" au clic sur Approuver', async () => {
    vi.mocked(listPendingDrafts).mockResolvedValue([sampleDraft]);
    vi.mocked(updateDraftStatus).mockResolvedValue({ ...sampleDraft, status: 'approved' });

    renderPage();

    const approveBtn = await screen.findByText('Approuver');
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(updateDraftStatus).toHaveBeenCalledWith('d1', 'approved');
    });
  });

  it('appelle exportHeyReachCsv au clic sur "Exporter CSV HeyReach" (filtre "Toutes" => brand undefined)', async () => {
    vi.mocked(listPendingDrafts).mockResolvedValue([sampleDraft]);
    vi.mocked(exportHeyReachCsv).mockResolvedValue({
      blob: new Blob(['col\n'], { type: 'text/csv' }),
      filename: 'heyreach_all.csv',
      skipped: 0,
    });

    // jsdom n'implemente pas createObjectURL/revokeObjectURL : on les stub.
    const createObjectURL = vi.fn(() => 'blob:mock');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });

    renderPage();

    const exportBtn = await screen.findByText('Exporter CSV HeyReach');
    fireEvent.click(exportBtn);

    await waitFor(() => {
      // Filtre par defaut = 'Toutes' => aucun brand transmis (undefined).
      expect(exportHeyReachCsv).toHaveBeenCalledWith(undefined);
    });
    expect(createObjectURL).toHaveBeenCalledTimes(1);

    vi.unstubAllGlobals();
  });

  it('affiche une note quand des leads sont ignorés (skipped > 0)', async () => {
    vi.mocked(listPendingDrafts).mockResolvedValue([sampleDraft]);
    vi.mocked(exportHeyReachCsv).mockResolvedValue({
      blob: new Blob(['col\n'], { type: 'text/csv' }),
      filename: 'heyreach_all.csv',
      skipped: 3,
    });

    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:mock'),
      revokeObjectURL: vi.fn(),
    });

    renderPage();

    const exportBtn = await screen.findByText('Exporter CSV HeyReach');
    fireEvent.click(exportBtn);

    expect(await screen.findByText(/3 leads ignorés/)).toBeInTheDocument();

    vi.unstubAllGlobals();
  });

  it('affiche une erreur inline si l\'export échoue (pas d\'écran blanc)', async () => {
    vi.mocked(listPendingDrafts).mockResolvedValue([sampleDraft]);
    vi.mocked(exportHeyReachCsv).mockRejectedValue(new Error('boom'));

    renderPage();

    const exportBtn = await screen.findByText('Exporter CSV HeyReach');
    fireEvent.click(exportBtn);

    expect(await screen.findByText(/Échec de l'export CSV/)).toBeInTheDocument();
  });
});
