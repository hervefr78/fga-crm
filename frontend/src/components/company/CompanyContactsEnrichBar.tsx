// =============================================================================
// FGA CRM - Company : barre d'enrichissement de l'onglet Contacts (contacts existants)
// =============================================================================
// Quand une societe a DEJA des contacts : point d'entree permanent pour (re)lancer
// la recherche des decideurs et de leurs emails (enrichissement Icypeas). Complete
// l'etat vide (CompanyContactsEmpty) qui ne s'affiche que sans aucun contact — sans
// cette barre, une societe dont les decideurs ont ete enregistres SANS email
// (domaine manquant) n'avait plus aucun moyen de relancer la recherche d'emails.
// Reutilise le meme hook useCompanyContactEnrichment (etats remontes par props).
// =============================================================================

import { Sparkles, Mail, Users } from 'lucide-react';

import { Button } from '../ui';
import type { EnrichmentJobStatus } from '../../types/enrichment';

interface CompanyContactsEnrichBarProps {
  // Nombre de contacts sans email (decideurs a completer).
  noEmailCount: number;
  isEnriching: boolean;
  lastStatus: EnrichmentJobStatus | null;
  // Nb d'emails trouves par le dernier job 'done' (null si aucun job termine) :
  // distingue "emails ajoutes" de "rien trouve".
  lastEmailsFound: number | null;
  quotaExceeded: boolean;
  sirenNotFound: boolean;
  isError: boolean;
  onEnrich: () => void;
}

export function CompanyContactsEnrichBar({
  noEmailCount,
  isEnriching,
  lastStatus,
  lastEmailsFound,
  quotaExceeded,
  sirenNotFound,
  isError,
  onEnrich,
}: CompanyContactsEnrichBarProps) {
  const hasMissing = noEmailCount > 0;

  // Message principal : contextualise selon les emails manquants.
  const title = hasMissing
    ? `${noEmailCount} contact${noEmailCount > 1 ? 's' : ''} sans email professionnel`
    : "Rechercher d'autres decideurs";

  // Libelle du bouton.
  const label = isEnriching
    ? 'Recherche en cours...'
    : hasMissing
      ? 'Chercher les emails manquants'
      : 'Enrichir les decideurs';

  // Message secondaire selon l'etat courant. Sur un job 'done', on distingue
  // "emails ajoutes" / "rien trouve" (evite un message contradictoire avec un
  // compteur "N sans email" toujours affiche).
  let hint: string | null = null;
  if (quotaExceeded) {
    hint = "Quota journalier d'enrichissement depasse. Reessayez plus tard.";
  } else if (sirenNotFound) {
    hint = 'SIREN introuvable automatiquement — renseignez-le sur la fiche.';
  } else if (isError) {
    hint = "La recherche n'a pas pu demarrer. Reessayez.";
  } else if (lastStatus === 'failed') {
    hint = 'La recherche des decideurs a echoue.';
  } else if (lastStatus === 'done') {
    if (lastEmailsFound && lastEmailsFound > 0) {
      hint = `${lastEmailsFound} email${lastEmailsFound > 1 ? 's' : ''} ajoute${lastEmailsFound > 1 ? 's' : ''}.`;
    } else if (hasMissing) {
      hint = 'Aucun nouvel email trouve pour ces contacts.';
    } else {
      hint = 'Recherche terminee — la liste est a jour.';
    }
  }

  // Icone contextuelle (convention projet : Users = decideurs, Mail = emails).
  const HeaderIcon = hasMissing ? Mail : Users;

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-slate-50/70 border-b border-slate-100">
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-600 flex items-center gap-1.5">
          <HeaderIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span className="truncate">{title}</span>
        </p>
        {hint && <p className="text-[11px] text-slate-400 mt-0.5">{hint}</p>}
      </div>
      <Button
        variant="secondary"
        size="sm"
        icon={Sparkles}
        loading={isEnriching}
        disabled={isEnriching}
        onClick={onEnrich}
        className="shrink-0"
      >
        {label}
      </Button>
    </div>
  );
}
