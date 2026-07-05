// =============================================================================
// FGA CRM - Company : hook recherche des decideurs (enrichissement Icypeas)
// =============================================================================
// Depuis une fiche societe SANS contact : declenche l'enrichissement des
// decideurs (CEO/CTO/CMO/CPO) via POST /enrichment/companies/{siren}/enrich
// (job async Celery), poll le statut, et rafraichit les contacts a la fin.
// =============================================================================

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { enrichCompanyById, getEnrichmentJob } from '../../api/enrichment';
import type { EnrichmentJob, EnrichmentJobStatus } from '../../types/enrichment';

const POLL_INTERVAL_MS = 2000;

// Statuts terminaux du job d'enrichissement.
const isTerminal = (s?: EnrichmentJobStatus): boolean => s === 'done' || s === 'failed';

interface UseCompanyContactEnrichmentParams {
  companyId?: string;
}

interface UseCompanyContactEnrichmentResult {
  // Declenche la recherche.
  enrich: () => void;
  // true tant que le job est en cours (mutation + polling).
  isEnriching: boolean;
  // Dernier statut terminal observe ('done' | 'failed'), null sinon.
  lastStatus: EnrichmentJobStatus | null;
  // Quota journalier d'enrichissement depasse (429).
  quotaExceeded: boolean;
  // SIREN introuvable automatiquement (422) : a renseigner sur la fiche.
  sirenNotFound: boolean;
  // Erreur au declenchement (hors quota / siren introuvable).
  isError: boolean;
}

export function useCompanyContactEnrichment({
  companyId,
}: UseCompanyContactEnrichmentParams): UseCompanyContactEnrichmentResult {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [lastStatus, setLastStatus] = useState<EnrichmentJobStatus | null>(null);

  const startMutation = useMutation({
    mutationFn: () => enrichCompanyById(companyId as string),
    onSuccess: (job: EnrichmentJob) => {
      setLastStatus(null);
      setJobId(job.id);
    },
  });

  const { data: job } = useQuery({
    queryKey: ['enrichment-job', jobId],
    queryFn: () => getEnrichmentJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => (isTerminal(q.state.data?.status) ? false : POLL_INTERVAL_MS),
  });

  // A la fin du job : si 'done', rafraichir les contacts (les decideurs trouves
  // apparaissent) + la fiche + l'AI ; puis arreter le polling.
  useEffect(() => {
    if (!jobId || !job || !isTerminal(job.status)) return;
    if (job.status === 'done') {
      void queryClient.invalidateQueries({ queryKey: ['contacts'] });
      void queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      void queryClient.invalidateQueries({ queryKey: ['next-action', 'company', companyId] });
    }
    setLastStatus(job.status);
    setJobId(null);
  }, [job, jobId, companyId, queryClient]);

  const isEnriching = startMutation.isPending || (!!jobId && !isTerminal(job?.status));
  const errStatus =
    (startMutation.error as { response?: { status?: number } } | null)?.response?.status;
  const quotaExceeded = errStatus === 429;
  const sirenNotFound = errStatus === 422;

  return {
    enrich: () => {
      if (companyId) startMutation.mutate();
    },
    isEnriching,
    lastStatus,
    quotaExceeded,
    sirenNotFound,
    isError: startMutation.isError && !quotaExceeded && !sirenNotFound,
  };
}
