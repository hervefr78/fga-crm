// =============================================================================
// FGA CRM - Tests useCompanyBulkAction (actions groupees audit / contacts)
// =============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import type { Company } from '../../types';

vi.mock('../../api/client', () => ({
  generateCompanyAudit: vi.fn(),
  getCompanyAuditGenerateStatus: vi.fn(),
  triggerCompanyAudit: vi.fn(),
}));
vi.mock('../../api/enrichment', () => ({
  enrichCompanyById: vi.fn(),
  getEnrichmentJob: vi.fn(),
}));

import {
  generateCompanyAudit, getCompanyAuditGenerateStatus, triggerCompanyAudit,
} from '../../api/client';
import { enrichCompanyById, getEnrichmentJob } from '../../api/enrichment';
import { useCompanyBulkAction, isAuditEligible, MAX_IMPORT_ATTEMPTS } from './useCompanyBulkAction';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const co = (id: string, name: string, sr: string | null): Company =>
  ({ id, name, startup_radar_id: sr } as Company);

describe('isAuditEligible', () => {
  it('vrai si startup_radar_id present (hors inv:)', () => {
    expect(isAuditEligible({ startup_radar_id: 'sr-123' })).toBe(true);
    expect(isAuditEligible({ startup_radar_id: null })).toBe(false);
    expect(isAuditEligible({ startup_radar_id: 'inv:9' })).toBe(false);
  });
});

describe('useCompanyBulkAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it('audit : non-eligible -> skipped, eligible -> running puis done (import)', async () => {
    vi.mocked(generateCompanyAudit).mockResolvedValue({});
    vi.mocked(getCompanyAuditGenerateStatus).mockResolvedValue({ status: 'completed', step: '', error: null });
    vi.mocked(triggerCompanyAudit).mockResolvedValue({});

    const { result } = renderHook(() => useCompanyBulkAction(), { wrapper });

    act(() => {
      result.current.startAudit([co('a', 'Eligible', 'sr1'), co('b', 'NoSR', null)]);
    });

    // Classification immediate.
    expect(result.current.tasks.find((t) => t.id === 'b')?.status).toBe('skipped');
    expect(result.current.tasks.find((t) => t.id === 'a')?.status).toBe('running');

    // Flush le pool de lancement (async) : generation fired sur l'eligible seulement.
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(generateCompanyAudit).toHaveBeenCalledWith('a');
    expect(generateCompanyAudit).not.toHaveBeenCalledWith('b');

    // Un tick de polling : completed -> import -> done.
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(triggerCompanyAudit).toHaveBeenCalledWith('a');
    expect(result.current.tasks.find((t) => t.id === 'a')?.status).toBe('done');
    expect(result.current.summary).toMatchObject({ done: 1, skipped: 1, running: 0 });
    expect(result.current.isRunning).toBe(false);
  });

  it('contacts : lance un job par entreprise puis passe a done', async () => {
    vi.mocked(enrichCompanyById).mockResolvedValue({ id: 'job1', status: 'running' } as never);
    vi.mocked(getEnrichmentJob).mockResolvedValue({ id: 'job1', status: 'done' } as never);

    const { result } = renderHook(() => useCompanyBulkAction(), { wrapper });

    act(() => { result.current.startContacts([co('a', 'Co', null)]); });

    // Flush le pool (enrichCompanyById) puis le .then(jobId).
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(enrichCompanyById).toHaveBeenCalledWith('a');
    expect(result.current.tasks[0].jobId).toBe('job1');
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(result.current.tasks[0].status).toBe('done');
  });

  it('audit : erreur de generation (hors 409) -> failed', async () => {
    vi.mocked(generateCompanyAudit).mockRejectedValue({ response: { status: 500 } });

    const { result } = renderHook(() => useCompanyBulkAction(), { wrapper });
    act(() => { result.current.startAudit([co('a', 'Boom', 'sr1')]); });

    // Flush la microtache generateCompanyAudit().catch(failed).
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(result.current.tasks[0].status).toBe('failed');
  });

  it('audit : import en echec repete -> failed apres le cap (pas de retry infini)', async () => {
    vi.mocked(generateCompanyAudit).mockResolvedValue({});
    vi.mocked(getCompanyAuditGenerateStatus).mockResolvedValue({ status: 'completed', step: '', error: null });
    vi.mocked(triggerCompanyAudit).mockRejectedValue(new Error('import KO'));

    const { result } = renderHook(() => useCompanyBulkAction(), { wrapper });
    act(() => { result.current.startAudit([co('a', 'Eligible', 'sr1')]); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    // Chaque cycle : completed -> import KO -> attempt++. Termine 'failed' au cap.
    for (let i = 0; i < MAX_IMPORT_ATTEMPTS; i++) {
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    }
    expect(result.current.tasks[0].status).toBe('failed');
    expect(result.current.isRunning).toBe(false);
  });
});
