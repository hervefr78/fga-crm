// =============================================================================
// FGA CRM - Tests InsightsCard (synthese hebdo IA du dashboard)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../api/client', () => ({
  getWeeklyInsights: vi.fn(),
}));

import { getWeeklyInsights } from '../../api/client';
import InsightsCard from './InsightsCard';

const INSIGHTS = {
  headline: '2 deals stagnent en proposal.',
  pipeline_health: 'Pipeline stable vs semaine precedente.',
  stale_deals_summary: 'Deal X inactif depuis 12 jours.',
  loss_patterns: null,
  top_actions: ['Relancer Deal X', 'Qualifier les nouveaux leads'],
  data_caveats: ['Moins de 5 deals perdus : pas de pattern fiable.'],
  period_days: 7,
  generated_at: '2026-07-08T09:00:00Z',
  cached: false,
  meta: { model: 'gpt-4o-mini', prompt_version: 'insights-v1' },
};

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <InsightsCard />
    </QueryClientProvider>,
  );
}

describe('InsightsCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('affiche la synthese (headline, actions numerotees, caveats)', async () => {
    vi.mocked(getWeeklyInsights).mockResolvedValue(INSIGHTS);
    renderCard();
    expect(await screen.findByText('2 deals stagnent en proposal.')).toBeInTheDocument();
    expect(screen.getByText('Relancer Deal X')).toBeInTheDocument();
    expect(screen.getByText(/pas de pattern fiable/)).toBeInTheDocument();
    expect(getWeeklyInsights).toHaveBeenCalledWith(false);
  });

  it('endpoint indisponible : message degrade, pas de crash', async () => {
    vi.mocked(getWeeklyInsights).mockRejectedValue(new Error('502'));
    renderCard();
    expect(await screen.findByText(/Synthèse indisponible/)).toBeInTheDocument();
  });

  it('Actualiser force la regeneration (refresh=true)', async () => {
    vi.mocked(getWeeklyInsights).mockResolvedValue(INSIGHTS);
    renderCard();
    await screen.findByText('2 deals stagnent en proposal.');
    fireEvent.click(screen.getByText('Actualiser'));
    await waitFor(() => expect(getWeeklyInsights).toHaveBeenCalledWith(true));
  });
});
