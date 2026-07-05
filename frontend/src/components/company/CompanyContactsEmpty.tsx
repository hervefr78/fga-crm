// =============================================================================
// FGA CRM - Company : etat vide de l'onglet Contacts + CTA enrichissement
// =============================================================================
// Quand une societe n'a aucun contact : propose de rechercher ses decideurs
// (CEO/CTO/CMO/CPO) + emails via l'enrichissement Icypeas (hook
// useCompanyContactEnrichment). Etats geres : SIREN present/absent, en cours,
// quota depasse, erreur, aucun resultat.
// =============================================================================

import { Users, Sparkles } from 'lucide-react';

import { Button } from '../ui';
import type { EnrichmentJobStatus } from '../../types/enrichment';

interface CompanyContactsEmptyProps {
  hasSiren: boolean;
  isEnriching: boolean;
  lastStatus: EnrichmentJobStatus | null;
  quotaExceeded: boolean;
  isError: boolean;
  onEnrich: () => void;
}

export function CompanyContactsEmpty({
  hasSiren,
  isEnriching,
  lastStatus,
  quotaExceeded,
  isError,
  onEnrich,
}: CompanyContactsEmptyProps) {
  // Message secondaire selon l'etat courant.
  let hint: string | null = null;
  if (!hasSiren) {
    hint = 'Renseignez le SIREN de la societe pour rechercher automatiquement ses decideurs.';
  } else if (quotaExceeded) {
    hint = "Quota journalier d'enrichissement depasse. Reessayez plus tard.";
  } else if (isError) {
    hint = "La recherche n'a pas pu demarrer. Reessayez.";
  } else if (lastStatus === 'failed') {
    hint = 'La recherche des decideurs a echoue.';
  } else if (lastStatus === 'done') {
    hint = 'Aucun decideur trouve pour cette societe.';
  }

  const label = isEnriching
    ? 'Recherche des decideurs...'
    : 'Chercher les decideurs (CEO/CTO/CMO/CPO)';

  return (
    <div className="py-10 flex flex-col items-center justify-center text-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-slate-50 flex items-center justify-center">
        <Users className="w-4 h-4 text-slate-400" />
      </div>
      <p className="text-sm text-slate-400">Aucun contact attache</p>

      {hasSiren && (
        <Button
          variant="secondary"
          size="sm"
          icon={Sparkles}
          loading={isEnriching}
          disabled={isEnriching}
          onClick={onEnrich}
        >
          {label}
        </Button>
      )}

      {hint && <p className="text-xs text-slate-400 max-w-xs">{hint}</p>}
    </div>
  );
}
