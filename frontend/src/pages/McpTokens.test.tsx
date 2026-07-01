// =============================================================================
// FGA CRM - Tests page Conso API MCP (dashboard cout par tool)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { McpUsageSummary, McpUsageByTool } from '../types';

vi.mock('../api/client', () => ({
  getMcpUsageSummary: vi.fn(),
  getMcpUsageByTool: vi.fn(),
}));

import { getMcpUsageSummary, getMcpUsageByTool } from '../api/client';
import McpTokensPage from './McpTokens';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <McpTokensPage />
    </QueryClientProvider>,
  );
}

const SUMMARY: McpUsageSummary = {
  date_from: '2026-07-01',
  date_to: '2026-07-01',
  total: {
    calls: 17,
    tokens_in: 2113,
    tokens_out: 407,
    cache_read: 0,
    cache_write: 0,
    cost_eur: 0.0021,
  },
  by_tool: [
    {
      tool_name: 'unipile_get_messages',
      calls: 17,
      input_tokens: 2113,
      output_tokens: 407,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      cost_eur: 0.0021,
    },
    {
      tool_name: 'nomo_generate_linkedin_message',
      calls: 3,
      input_tokens: 900,
      output_tokens: 1200,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      cost_eur: 0.021,
    },
  ],
};

describe('McpTokensPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('affiche les KPI et la liste des tools quand il y a de la conso', async () => {
    vi.mocked(getMcpUsageSummary).mockResolvedValue(SUMMARY);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText('unipile_get_messages')).toBeInTheDocument(),
    );
    // Les deux tools sont listés + les libellés KPI présents.
    expect(screen.getByText('nomo_generate_linkedin_message')).toBeInTheDocument();
    expect(screen.getByText('Cout total')).toBeInTheDocument();
    expect(screen.getByText('Appels LLM')).toBeInTheDocument();
  });

  it("affiche l'état vide quand aucune conso", async () => {
    vi.mocked(getMcpUsageSummary).mockResolvedValue({
      ...SUMMARY,
      total: { calls: 0, tokens_in: 0, tokens_out: 0, cache_read: 0, cache_write: 0, cost_eur: 0 },
      by_tool: [],
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/Aucune consommation/i)).toBeInTheDocument(),
    );
  });

  it('déplie un tool et charge son détail par modèle', async () => {
    vi.mocked(getMcpUsageSummary).mockResolvedValue(SUMMARY);
    const detail: McpUsageByTool = {
      tool_name: 'unipile_get_messages',
      date_from: '2026-07-01',
      date_to: '2026-07-01',
      rows: [
        {
          day: '2026-07-01',
          model: 'claude-haiku-4-5-20251001',
          calls: 17,
          input_tokens: 2113,
          output_tokens: 407,
          cache_read_tokens: 0,
          cache_write_tokens: 0,
          cost_eur: 0.0021,
        },
      ],
    };
    vi.mocked(getMcpUsageByTool).mockResolvedValue(detail);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText('unipile_get_messages')).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText('unipile_get_messages'));

    await waitFor(() =>
      expect(screen.getByText('claude-haiku-4-5-20251001')).toBeInTheDocument(),
    );
    expect(getMcpUsageByTool).toHaveBeenCalledWith(
      'unipile_get_messages',
      expect.any(String),
      expect.any(String),
    );
  });
});
