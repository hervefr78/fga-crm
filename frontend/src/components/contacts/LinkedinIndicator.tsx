// =============================================================================
// FGA CRM - Indicateur de fiabilite LinkedIn URL (Phase B 2026-05)
// =============================================================================
// Affiche un badge a cote du lien LinkedIn pour signaler si l'URL est verifiee
// ou generee automatiquement (a verifier avant prospection).

import { Badge } from '../ui';

interface LinkedinIndicatorProps {
  status: string | null | undefined;
}

export default function LinkedinIndicator({ status }: LinkedinIndicatorProps) {
  if (!status) return null;

  if (status === 'verified') {
    return <Badge variant="success">Vérifié</Badge>;
  }

  if (status === 'candidate') {
    return (
      <span title="URL LinkedIn générée automatiquement à partir du nom. À vérifier manuellement avant prospection.">
        <Badge variant="warning">À vérifier</Badge>
      </span>
    );
  }

  if (status === 'invalid') {
    return (
      <span title="URL LinkedIn signalée comme invalide.">
        <Badge variant="danger">Invalide</Badge>
      </span>
    );
  }

  return null;
}
