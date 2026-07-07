// =============================================================================
// FGA CRM - Companies : actions groupees (audit SR / recherche de contacts)
// =============================================================================
// Lance une action sur N entreprises selectionnees puis suit la progression
// (polling par entreprise) : "lancer + notifier" ET "suivi de progression".
//
// Robustesse (durcissement post-review) :
//  - Boucle AUTO-PLANIFIEE (setTimeout re-arme APRES chaque cycle) : pas de
//    chevauchement de ticks, donc pas de double triggerCompanyAudit (double import).
//  - Bornes (DC1) : deadline globale (MAX_POLL_CYCLES) + cap d'essais d'import
//    (MAX_IMPORT_ATTEMPTS) -> jamais de tache coincee 'running' a l'infini.
//  - Lancements throttles (pool de concurrence) : pas de rafale de N POST couteux.
//  - Invalidation de la liste UNE fois en fin d'action (pas a chaque tache).
// =============================================================================

import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import {
  generateCompanyAudit, getCompanyAuditGenerateStatus, triggerCompanyAudit,
} from '../../api/client';
import { enrichCompanyById, getEnrichmentJob } from '../../api/enrichment';
import type { Company } from '../../types';

const POLL_INTERVAL_MS = 5000;
const MAX_LAUNCH_CONCURRENCY = 4;      // POST de lancement simultanes max
const MAX_POLL_CYCLES = 240;           // deadline globale : 240 * 5s = 20 min
export const MAX_IMPORT_ATTEMPTS = 3;  // essais d'import audit avant echec

export type BulkActionType = 'audit' | 'contacts';
export type BulkTaskStatus = 'running' | 'done' | 'failed' | 'skipped';

export interface BulkTask {
  id: string;
  name: string;
  status: BulkTaskStatus;
  jobId?: string;   // enrichissement : id du job a poller
}

export interface BulkSummary {
  total: number;
  running: number;
  done: number;
  failed: number;
  skipped: number;
}

interface UseCompanyBulkActionResult {
  action: BulkActionType | null;
  tasks: BulkTask[];
  summary: BulkSummary;
  isRunning: boolean;
  startAudit: (companies: Company[]) => void;
  startContacts: (companies: Company[]) => void;
  reset: () => void;
}

// Audit SR possible uniquement si la societe est liee a Startup Radar
// (les ids 'inv:*' sont des investisseurs, pas auditables — cf. canAudit fiche).
export function isAuditEligible(c: Pick<Company, 'startup_radar_id'>): boolean {
  return !!c.startup_radar_id && !c.startup_radar_id.startsWith('inv:');
}

function summarize(tasks: BulkTask[]): BulkSummary {
  return {
    total: tasks.length,
    running: tasks.filter((t) => t.status === 'running').length,
    done: tasks.filter((t) => t.status === 'done').length,
    failed: tasks.filter((t) => t.status === 'failed').length,
    skipped: tasks.filter((t) => t.status === 'skipped').length,
  };
}

// Execute `worker` sur `items` avec au plus `limit` en vol simultanement.
async function runPool<T>(items: T[], limit: number, worker: (item: T) => Promise<void>) {
  let i = 0;
  const next = async (): Promise<void> => {
    const idx = i++;
    if (idx >= items.length) return;
    await worker(items[idx]);
    return next();
  };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, next));
}

export function useCompanyBulkAction(): UseCompanyBulkActionResult {
  const queryClient = useQueryClient();
  const [action, setAction] = useState<BulkActionType | null>(null);
  const [tasks, setTasks] = useState<BulkTask[]>([]);
  // Ref lue par la boucle de polling (evite de re-souscrire a chaque update).
  const tasksRef = useRef<BulkTask[]>([]);
  tasksRef.current = tasks;
  const pollCyclesRef = useRef(0);
  const importAttemptsRef = useRef<Record<string, number>>({});
  const wasRunningRef = useRef(false);

  const patchTask = (id: string, patch: Partial<BulkTask>) =>
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));

  const begin = (type: BulkActionType, initial: BulkTask[]) => {
    pollCyclesRef.current = 0;
    importAttemptsRef.current = {};
    setAction(type);
    setTasks(initial);
  };

  const startAudit = (companies: Company[]) => {
    begin('audit', companies.map((c) => ({
      id: c.id, name: c.name, status: isAuditEligible(c) ? 'running' : 'skipped',
    })));
    const eligible = companies.filter(isAuditEligible);
    // Lancements throttles (409 = deja en cours -> on poll quand meme).
    void runPool(eligible, MAX_LAUNCH_CONCURRENCY, async (c) => {
      try {
        await generateCompanyAudit(c.id);
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status !== 409) patchTask(c.id, { status: 'failed' });
      }
    });
  };

  const startContacts = (companies: Company[]) => {
    begin('contacts', companies.map((c) => ({ id: c.id, name: c.name, status: 'running' })));
    void runPool(companies, MAX_LAUNCH_CONCURRENCY, async (c) => {
      try {
        const job = await enrichCompanyById(c.id);
        patchTask(c.id, { jobId: job.id });
      } catch {
        patchTask(c.id, { status: 'failed' });
      }
    });
  };

  const reset = () => {
    setAction(null);
    setTasks([]);
  };

  // Boucle de polling auto-planifiee : le tick suivant n'est arme qu'APRES la fin
  // du precedent (pas de chevauchement). Deadline + cap d'import bornent la boucle.
  const hasRunning = tasks.some((t) => t.status === 'running');
  useEffect(() => {
    if (!action || !hasRunning) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      pollCyclesRef.current += 1;
      const timedOut = pollCyclesRef.current > MAX_POLL_CYCLES;
      const running = tasksRef.current.filter((t) => t.status === 'running');
      for (const t of running) {
        if (cancelled) return;
        if (timedOut) { patchTask(t.id, { status: 'failed' }); continue; }
        try {
          if (action === 'audit') {
            const s = await getCompanyAuditGenerateStatus(t.id);
            if (s.status === 'completed') {
              try {
                await triggerCompanyAudit(t.id); // import du resultat dans le CRM
                patchTask(t.id, { status: 'done' });
              } catch {
                const n = (importAttemptsRef.current[t.id] ?? 0) + 1;
                importAttemptsRef.current[t.id] = n;
                if (n >= MAX_IMPORT_ATTEMPTS) patchTask(t.id, { status: 'failed' });
              }
            } else if (s.status === 'failed') {
              patchTask(t.id, { status: 'failed' });
            }
            // 'idle' / 'running' / 'pending' : on continue (borne par la deadline)
          } else {
            if (!t.jobId) continue; // job pas encore cree (enrichCompanyById en vol)
            const job = await getEnrichmentJob(t.jobId);
            if (job.status === 'done') patchTask(t.id, { status: 'done' });
            else if (job.status === 'failed') patchTask(t.id, { status: 'failed' });
          }
        } catch {
          // Erreur transitoire (reseau) : on retente au cycle suivant.
        }
      }
      if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    timer = setTimeout(poll, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [action, hasRunning]);

  // Invalidation de la liste UNE fois quand l'action se termine (running -> false).
  useEffect(() => {
    if (action && wasRunningRef.current && !hasRunning) {
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
    }
    wasRunningRef.current = hasRunning;
  }, [action, hasRunning, queryClient]);

  return {
    action,
    tasks,
    summary: summarize(tasks),
    isRunning: hasRunning,
    startAudit,
    startContacts,
    reset,
  };
}
