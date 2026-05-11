// =============================================================================
// FGA CRM - Indicateur de fiabilite Email (Phase B 2026-05)
// =============================================================================
// Affiche un badge a cote de l'email du contact pour signaler le niveau de
// confiance (Verifie / Candidat / Risque) en fonction de email_status et
// email_pattern_used (synced from Startup Radar enrichment).

import { Badge } from '../ui';

interface EmailIndicatorProps {
  emailStatus: string | null | undefined;
  emailPattern?: string | null;
}

export default function EmailIndicator({ emailStatus, emailPattern }: EmailIndicatorProps) {
  if (!emailStatus) return null;

  if (emailStatus === 'valid') {
    return <Badge variant="success">Vérifié</Badge>;
  }

  if (emailStatus === 'unknown') {
    // Email genere par heuristique — fiabilite limitee
    const tip = emailPattern
      ? `Email généré par heuristique (pattern : ${emailPattern}). À vérifier avant envoi.`
      : 'Email non vérifié. À valider avant envoi.';
    return (
      <span title={tip}>
        <Badge variant="warning">Candidat</Badge>
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
