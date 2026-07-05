// =============================================================================
// FGA CRM - Company : banniere de statut generation/import d'audit SR
// (extrait de CompanyDetail.tsx — JSX iso-comportement)
// Presentationnel : recoit l'etat du hook + de la mutation d'import en props.
// =============================================================================

import { Zap, AlertCircle } from 'lucide-react';

import type { AuditGenerateStatus, CompanyAuditResponse } from '../../types';

interface CompanyAuditBannerProps {
  isGeneratingAudit: boolean;
  auditGenStatus: AuditGenerateStatus | undefined;
  // Etat de la mutation d'import (auditMutation), portee par la page.
  importSuccess: boolean;
  importResult: CompanyAuditResponse | undefined;
  importError: boolean;
  importErrorMessage?: string;
}

export default function CompanyAuditBanner({
  isGeneratingAudit,
  auditGenStatus,
  importSuccess,
  importResult,
  importError,
  importErrorMessage,
}: CompanyAuditBannerProps) {
  return (
    <>
      {/* Generation d'audit en cours (pipeline SR) */}
      {isGeneratingAudit && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-sm text-indigo-700 flex items-center gap-2">
          <Zap className="w-4 h-4 flex-shrink-0 animate-pulse" />
          <span>
            Generation de l'audit en cours cote Startup Radar
            {auditGenStatus?.step ? ` — ${auditGenStatus.step}` : '...'}
          </span>
        </div>
      )}
      {/* Echec de generation */}
      {!isGeneratingAudit && auditGenStatus?.status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{auditGenStatus.error || 'La generation de l\'audit a echoue.'}</span>
        </div>
      )}

      {/* Audit feedback (import result) */}
      {!isGeneratingAudit && importSuccess && importResult && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm text-emerald-700">
          {importResult.audits_created > 0 && (
            <span>{importResult.audits_created} audit{importResult.audits_created > 1 ? 's' : ''} cree{importResult.audits_created > 1 ? 's' : ''}</span>
          )}
          {importResult.audits_skipped > 0 && (
            <span>{importResult.audits_created > 0 ? ' — ' : ''}{importResult.audits_skipped} deja existant{importResult.audits_skipped > 1 ? 's' : ''}</span>
          )}
          {importResult.audits_created === 0 && importResult.audits_skipped === 0 && (
            <span>Aucun audit disponible pour cette entreprise</span>
          )}
        </div>
      )}
      {importError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{importErrorMessage || 'Erreur lors du lancement de l\'audit'}</span>
        </div>
      )}
    </>
  );
}
