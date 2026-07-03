// =============================================================================
// FGA CRM - Indicateur de fiabilite Email (Phase B 2026-05)
// =============================================================================
// Affiche un badge a cote de l'email du contact pour signaler le niveau de
// confiance (Verifie / Candidat / Risque) en fonction de email_status,
// email_pattern_used et enrichment_source (synced from Startup Radar).
//
// Flag "pas fiable" : quand l'email vient d'une heuristique non verifiee
// (scraped_founders), un second badge orange s'affiche pour avertir
// le commercial que l'email n'a pas ete valide — risque de bounce eleve.
// Les emails evaboot sont deja passes par un verificateur → badge seul suffit.

import { Badge } from '../ui';

// Sources pour lesquelles l'email n'a PAS ete verifie par un outil tiers
const UNVERIFIED_SOURCES = new Set(['scraped_founders']);

interface EmailIndicatorProps {
  emailStatus: string | null | undefined;
  emailPattern?: string | null;
  enrichmentSource?: string | null;
}

export default function EmailIndicator({ emailStatus, emailPattern, enrichmentSource }: EmailIndicatorProps) {
  if (!emailStatus) return null;

  if (emailStatus === 'valid') {
    return <Badge variant="success">Vérifié</Badge>;
  }

  if (emailStatus === 'unknown') {
    const isHeuristic = enrichmentSource ? UNVERIFIED_SOURCES.has(enrichmentSource) : false;
    const sourceName = enrichmentSource === 'scraped_founders' ? 'scraping fondateurs'
      : emailPattern ? `pattern ${emailPattern}` : 'heuristique';

    const tip = isHeuristic
      ? `Email généré par ${sourceName} — non vérifié. Risque de bounce élevé avant envoi.`
      : emailPattern
        ? `Email généré par heuristique (pattern : ${emailPattern}). À vérifier avant envoi.`
        : 'Email non vérifié. À valider avant envoi.';

    return (
      <span className="inline-flex items-center gap-1">
        <span title={tip}>
          <Badge variant="warning">Candidat</Badge>
        </span>
        {isHeuristic && (
          <span title={tip}>
            <Badge variant="danger">Pas vérifié</Badge>
          </span>
        )}
      </span>
    );
  }

  if (emailStatus === 'risky' || emailStatus === 'invalid') {
    return (
      <span title="Email signalé comme risqué (catch-all, role-based, ou bounce probable).">
        <Badge variant="danger">Risqué</Badge>
      </span>
    );
  }

  return null;
}
