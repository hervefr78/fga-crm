// =============================================================================
// FGA CRM - Indicateur de fiabilite Email (Phase B 2026-05)
// =============================================================================
// Affiche un badge a cote de l'email du contact pour signaler le niveau de
// confiance (Verifie / Candidat / Risque) en fonction de email_status,
// email_pattern_used et enrichment_source (synced from Startup Radar).
//
// Flag "pas fiable" : quand l'email a ete DEVINE (source heuristique connue OU
// genere par un pattern), un second badge orange s'affiche pour avertir le
// commercial que l'email n'a pas ete valide — risque de bounce eleve.
// Le signal `email_pattern_used` couvre GENERIQUEMENT toute source (connue ou
// inconnue) ayant devine l'email -> fallback robuste face aux sources non listees.

import { Badge } from '../ui';

// Sources connues pour lesquelles l'email n'a PAS ete verifie par un outil tiers
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
    // Heuristique = email devine : source non verifiee connue OU genere par pattern.
    // Le pattern rend le flag robuste pour TOUTE source (y compris inconnue).
    const isKnownUnverified = enrichmentSource ? UNVERIFIED_SOURCES.has(enrichmentSource) : false;
    const isHeuristic = isKnownUnverified || Boolean(emailPattern);

    // Nom de source lisible, avec fallback generique pour toute source inconnue.
    const sourceName = enrichmentSource === 'scraped_founders' ? 'scraping fondateurs'
      : emailPattern ? `pattern ${emailPattern}`
      : enrichmentSource ? `source « ${enrichmentSource} »`
      : 'heuristique';

    const tip = isHeuristic
      ? `Email généré par ${sourceName} — non vérifié. Risque de bounce élevé avant envoi.`
      : enrichmentSource
        ? `Email de ${sourceName} — non vérifié. À valider avant envoi.`
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
