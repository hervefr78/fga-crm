// =============================================================================
// FGA CRM - Company : onglet Audit SR (extrait de CompanyDetail.tsx)
// Sous-tabs Messaging / Detaille / GEO + AuditResultPanel.
// La logique de generation (mutations + polling) reste dans la page.
// =============================================================================

import { FileSearch } from 'lucide-react';
import clsx from 'clsx';

import type { Activity } from '../../types';
import { Button } from '../ui';
import AuditResultPanel from '../audit/AuditResultPanel';
import { formatDate } from './companyUtils';

// Onglet Audit SR : sous-tabs Messaging / Detaille / GEO + AuditResultPanel.
// Reintegre la fonctionnalite preexistante (DC10 — metadata.audit_type).
export default function AuditTab({
  subTab, onSubTabChange,
  messaging, detailed, geo,
  canAudit, auditPending, onLaunchAudit,
}: {
  subTab: 'messaging' | 'detailed' | 'geo';
  onSubTabChange: (t: 'messaging' | 'detailed' | 'geo') => void;
  messaging: Activity[]; detailed: Activity[]; geo: Activity[];
  canAudit: boolean; auditPending: boolean; onLaunchAudit: () => void;
}) {
  const current = subTab === 'messaging' ? messaging : subTab === 'detailed' ? detailed : geo;
  const subTabs = [
    { key: 'messaging' as const, label: 'Messaging', count: messaging.length },
    { key: 'detailed' as const, label: 'Detaille', count: detailed.length },
    { key: 'geo' as const, label: 'GEO', count: geo.length },
  ];

  return (
    <div className="p-4 space-y-4">
      {/* Sous-tabs */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
          {subTabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => onSubTabChange(t.key)}
              className={clsx(
                'px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                subTab === t.key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700',
              )}
            >
              {t.label}
              {t.count > 0 && <span className="ml-1.5 text-xs text-slate-400">({t.count})</span>}
            </button>
          ))}
        </div>
        {canAudit && (
          <Button
            variant="secondary"
            size="sm"
            icon={FileSearch}
            onClick={onLaunchAudit}
            loading={auditPending}
          >
            Lancer un audit
          </Button>
        )}
      </div>

      {/* Contenu */}
      {current.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center text-slate-400">
          <FileSearch className="w-8 h-8 mx-auto mb-2" />
          <p className="text-sm">
            Aucun audit {subTab === 'messaging' ? 'messaging' : subTab === 'detailed' ? 'detaille' : 'GEO'} disponible
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {current.map((a) => (
            a.metadata_ ? (
              <AuditResultPanel
                key={a.id}
                metadata={a.metadata_}
                subject={a.subject || 'Audit'}
                createdAt={a.created_at}
                content={a.content || ''}
              />
            ) : (
              <div key={a.id} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                <p className="text-sm text-slate-700">{a.subject || 'Audit'}</p>
                {a.content && <p className="text-sm text-slate-500 mt-1">{a.content}</p>}
                <p className="text-xs text-slate-400 mt-2">{formatDate(a.created_at)}</p>
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}
