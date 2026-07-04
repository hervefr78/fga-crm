// =============================================================================
// FGA CRM - Company : hook generation d'audit SR a la demande
// (extrait de CompanyDetail.tsx — logique iso-comportement)
// Flux : trigger SR -> poll du statut -> import auto du resultat.
// La mutation d'import (auditMutation) reste portee par la page et est injectee
// ici via `importAudit` / `importPending`.
// =============================================================================

import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

import { generateCompanyAudit, getCompanyAuditGenerateStatus } from '../../api/client';
import type { AuditGenerateStatus } from '../../types';

interface UseCompanyAuditGenerationParams {
  companyId?: string;
  // Mutation d'import du resultat SR (auditMutation.mutate), portee par la page.
  importAudit: () => void;
  // Etat "import en cours" (auditMutation.isPending) — entre dans isAuditBusy.
  importPending: boolean;
  // Appele au demarrage de la generation (la page bascule sur l'onglet audit).
  onGenerateStart: () => void;
}

interface UseCompanyAuditGenerationResult {
  isGeneratingAudit: boolean;
  auditGenStatus: AuditGenerateStatus | undefined;
  generateAudit: () => void;
  isAuditBusy: boolean;
}

export function useCompanyAuditGeneration({
  companyId,
  importAudit,
  importPending,
  onGenerateStart,
}: UseCompanyAuditGenerationParams): UseCompanyAuditGenerationResult {
  const [isGeneratingAudit, setIsGeneratingAudit] = useState(false);

  const generateAuditMutation = useMutation({
    mutationFn: () => generateCompanyAudit(companyId!),
    onSuccess: () => {
      setIsGeneratingAudit(true);
      onGenerateStart();
    },
    onError: (err) => {
      // 409 = un audit tourne deja cote SR -> on poll quand meme
      if ((err as { response?: { status?: number } })?.response?.status === 409) {
        setIsGeneratingAudit(true);
        onGenerateStart();
      }
    },
  });

  const { data: auditGenStatus } = useQuery<AuditGenerateStatus>({
    queryKey: ['audit-generate-status', companyId],
    queryFn: () => getCompanyAuditGenerateStatus(companyId!),
    enabled: isGeneratingAudit && !!companyId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'completed' || s === 'failed' ? false : 5000;
    },
  });

  // Transitions du pipeline SR : completed -> importer le resultat ; failed -> stop
  useEffect(() => {
    if (!isGeneratingAudit) return;
    if (auditGenStatus?.status === 'completed') {
      setIsGeneratingAudit(false);
      importAudit();
    } else if (auditGenStatus?.status === 'failed') {
      setIsGeneratingAudit(false);
    }
  }, [auditGenStatus?.status, isGeneratingAudit, importAudit]);

  const isAuditBusy =
    generateAuditMutation.isPending || isGeneratingAudit || importPending;

  return {
    isGeneratingAudit,
    auditGenStatus,
    generateAudit: () => generateAuditMutation.mutate(),
    isAuditBusy,
  };
}
