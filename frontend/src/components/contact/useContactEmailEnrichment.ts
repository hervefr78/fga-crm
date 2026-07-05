// =============================================================================
// FGA CRM - Contact : hook recherche d'email (enrichissement Icypeas, mode contacts)
// =============================================================================
// Depuis une fiche contact SANS email : declenche la recherche de l'email via
// POST /enrichment/jobs {mode:'contacts', contact_ids:[id]} (Feature B), poll le
// statut, et rafraichit le contact a la fin.
// =============================================================================

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { enrichContactEmails, getEnrichmentJob } from '../../api/enrichment';
import type { EnrichmentJob, EnrichmentJobStatus } from '../../types/enrichment';

const POLL_INTERVAL_MS = 2000;

const isTerminal = (s?: EnrichmentJobStatus): boolean => s === 'done' || s === 'failed';

interface UseContactEmailEnrichmentParams {
  contactId?: string;
}

interface UseContactEmailEnrichmentResult {
  enrich: () => void;
  isEnriching: boolean;
  lastStatus: EnrichmentJobStatus | null;
  quotaExceeded: boolean;
  isError: boolean;
}

export function useContactEmailEnrichment({
  contactId,
}: UseContactEmailEnrichmentParams): UseContactEmailEnrichmentResult {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [lastStatus, setLastStatus] = useState<EnrichmentJobStatus | null>(null);

  const startMutation = useMutation({
    mutationFn: () => enrichContactEmails([contactId as string]),
    onSuccess: (job: EnrichmentJob) => {
      setLastStatus(null);
      setJobId(job.id);
    },
  });

  // La page ContactDetail ne remonte pas forcement en navigation (meme route
  // /contacts/:id) : reset de l'etat quand contactId change, sinon le statut/erreur
  // d'un contact fuirait sur le suivant.
  useEffect(() => {
    setJobId(null);
    setLastStatus(null);
    startMutation.reset();
    // startMutation hors deps volontairement (sa ref change a chaque transition
    // d'etat : l'inclure re-declencherait le reset en plein job).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contactId]);

  const { data: job } = useQuery({
    queryKey: ['enrichment-job', jobId],
    queryFn: () => getEnrichmentJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => (isTerminal(q.state.data?.status) ? false : POLL_INTERVAL_MS),
  });

  // A la fin : rafraichir le contact (l'email apparait) + la suggestion IA.
  useEffect(() => {
    if (!jobId || !job || !isTerminal(job.status)) return;
    if (job.status === 'done') {
      void queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      void queryClient.invalidateQueries({ queryKey: ['next-action', 'contact', contactId] });
      void queryClient.invalidateQueries({ queryKey: ['activities', { contact_id: contactId }] });
    }
    setLastStatus(job.status);
    setJobId(null);
  }, [job, jobId, contactId, queryClient]);

  const isEnriching = startMutation.isPending || (!!jobId && !isTerminal(job?.status));
  const quotaExceeded =
    (startMutation.error as { response?: { status?: number } } | null)?.response?.status === 429;

  return {
    enrich: () => {
      if (contactId) startMutation.mutate();
    },
    isEnriching,
    lastStatus,
    quotaExceeded,
    isError: startMutation.isError && !quotaExceeded,
  };
}
