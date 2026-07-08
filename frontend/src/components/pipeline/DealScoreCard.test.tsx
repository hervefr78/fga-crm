// =============================================================================
// FGA CRM - Tests DealScoreCard (carte Score IA du deal)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import type { Deal } from '../../types';

vi.mock('../../api/client', () => ({
  scoreDeal: vi.fn(),
}));

import { scoreDeal } from '../../api/client';
import DealScoreCard from './DealScoreCard';

const baseDeal = {
  id: 'd1', title: 'Deal', stage: 'new', amount: null, currency: 'EUR',
  probability: 0, priority: 'medium', expected_close_date: null,
  actual_close_date: null, position: 0, company_id: null, contact_id: null,
  owner_id: null, description: null, pricing_type: 'one_shot',
  recurring_amount: null, commitment_months: null, created_at: '2026-07-01',
  loss_reason: null, owner_name: null, company_name: null, contact_name: null,
  product: null, ai_score: null, ai_tier: null, ai_score_rationale: null,
  ai_score_missing: [], ai_scored_at: null, ai_score_meta: {},
} as Deal;

const scoredDeal: Deal = {
  ...baseDeal,
  ai_score: 72, ai_tier: 'A',
  ai_score_rationale: 'Post-levee, audit bas : opportunite mesuree.',
  ai_score_missing: ['effectif inconnu'],
  ai_scored_at: '2026-07-08T10:00:00Z',
  ai_score_meta: {
    model: 'gpt-4o-mini', prompt_version: 'scoring-v1',
    recommended_product: 'audit-999', fit_points: 40, intent_points: 20, message_points: 12,
  },
};

function renderCard(deal: Deal) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DealScoreCard deal={deal} />
    </QueryClientProvider>,
  );
}

describe('DealScoreCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('deal non score : etat vide + bouton Scorer', () => {
    renderCard(baseDeal);
    expect(screen.getByText(/Pas encore scoré/)).toBeInTheDocument();
    expect(screen.getByText('Scorer')).toBeInTheDocument();
  });

  it('deal score : score, tier, decomposition, rationale, produit recommande', () => {
    renderCard(scoredDeal);
    expect(screen.getByText('72')).toBeInTheDocument();
    expect(screen.getByText('Tier A')).toBeInTheDocument();
    expect(screen.getByText(/Fit 40\/50/)).toBeInTheDocument();
    expect(screen.getByText(/Intent 20\/30/)).toBeInTheDocument();
    expect(screen.getByText(/opportunite mesuree/)).toBeInTheDocument();
    expect(screen.getByText(/Audit clarté/)).toBeInTheDocument();
    expect(screen.getByText('Re-scorer')).toBeInTheDocument();
  });

  it('signaux manquants : replies par defaut, depliables au clic', () => {
    renderCard(scoredDeal);
    expect(screen.queryByText('effectif inconnu')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/1 signal manquant/));
    expect(screen.getByText('effectif inconnu')).toBeInTheDocument();
  });

  it('clic Scorer -> appelle scoreDeal (sans force au 1er score)', async () => {
    vi.mocked(scoreDeal).mockResolvedValue({});
    renderCard(baseDeal);
    fireEvent.click(screen.getByText('Scorer'));
    await waitFor(() => expect(scoreDeal).toHaveBeenCalledWith('d1', false));
  });

  it('clic Re-scorer -> force le re-scoring', async () => {
    vi.mocked(scoreDeal).mockResolvedValue({});
    renderCard(scoredDeal);
    fireEvent.click(screen.getByText('Re-scorer'));
    await waitFor(() => expect(scoreDeal).toHaveBeenCalledWith('d1', true));
  });

  it('echec du scoring : message d erreur', async () => {
    vi.mocked(scoreDeal).mockRejectedValue(new Error('502'));
    renderCard(baseDeal);
    fireEvent.click(screen.getByText('Scorer'));
    expect(await screen.findByText(/Scoring indisponible/)).toBeInTheDocument();
  });
});
