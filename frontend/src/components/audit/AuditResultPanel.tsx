// =============================================================================
// FGA CRM - Panneau de resultats d'audit Startup Radar
// Dispatch de la vue (messaging / detaille / GEO) selon audit_type + layout.
// Les vues et atomes sont extraits dans les fichiers du dossier components/audit/.
// =============================================================================

import { DetailedAuditView } from './DetailedAuditView';
import { GeoAuditView } from './GeoAuditView';
import { MessagingAuditView } from './MessagingAuditView';

// ---------------------------------------------------------------------------
// Composant principal
// ---------------------------------------------------------------------------

interface AuditResultPanelProps {
  metadata: Record<string, unknown>;
  subject: string;
  createdAt: string;
  content?: string;
}

export default function AuditResultPanel({ metadata, subject, createdAt, content = '' }: AuditResultPanelProps) {
  const auditType = (metadata.audit_type as string) ?? '';
  const formattedDate = new Date(createdAt).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">{subject}</h3>
        <span className="text-xs text-slate-400">{formattedDate}</span>
      </div>
      {/* Body */}
      <div className="p-5">
        {auditType === 'detailed' && <DetailedAuditView metadata={metadata} content={content} />}
        {auditType === 'messaging' && <MessagingAuditView metadata={metadata} />}
        {auditType === 'geo' && <GeoAuditView metadata={metadata} content={content} />}
        {!['detailed', 'messaging', 'geo'].includes(auditType) && (
          <p className="text-sm text-slate-400">Type d'audit inconnu : {auditType || '(vide)'}</p>
        )}
      </div>
    </div>
  );
}
