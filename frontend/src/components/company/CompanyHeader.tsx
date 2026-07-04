// =============================================================================
// FGA CRM - Company : en-tete (hero) de la colonne detail
// (extrait de CompanyDetail.tsx — JSX iso-comportement, meme rendu DOM)
// Presentationnel : recoit company, KPI derives et handlers en props.
// =============================================================================

import {
  MapPin, Edit2, Trash2, Plus, Zap,
  Target, Star, TrendingUp, Activity as ActivityIcon,
} from 'lucide-react';

import type { Company } from '../../types';
import { Badge, Button } from '../ui';
import { Kpi } from './CompanyAtoms';
import { formatRelative } from './companyUtils';

// KPI derives calcules (memoises) par la page et passes tels quels.
export interface CompanyKpi {
  pipeline: number;
  wonAmount: number;
  lastActivity?: string;
  dealsCount: number;
}

interface CompanyHeaderProps {
  company: Company;
  kpi: CompanyKpi;
  // Nombre d'activites hors audit (pour le KPI "Activite 30j").
  activityCount: number;
  canAudit: boolean;
  isAuditBusy: boolean;
  onEdit: () => void;
  onGenerateAudit: () => void;
  onNewDeal: () => void;
  onDelete: () => void;
}

export default function CompanyHeader({
  company,
  kpi,
  activityCount,
  canAudit,
  isAuditBusy,
  onEdit,
  onGenerateAudit,
  onNewDeal,
  onDelete,
}: CompanyHeaderProps) {
  return (
    <div className="space-y-5 pb-6 border-b border-slate-200">
      <div className="flex items-start gap-4">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 border border-slate-200 flex items-center justify-center text-2xl font-semibold text-slate-600">
          {company.name.slice(0, 2)}
        </div>
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="text-[11px] uppercase tracking-wider font-medium text-slate-400">
            Entreprise · {company.startup_radar_id ? 'Startup Radar' : 'Manuel'}
          </div>
          <h1 className="text-2xl font-semibold text-slate-900 tracking-tight flex items-center gap-3 flex-wrap">
            {company.name}
            {company.startup_radar_id && (
              <Badge variant="success">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1" />
                Active
              </Badge>
            )}
          </h1>
          <div className="flex items-center gap-2 flex-wrap text-sm text-slate-500">
            {company.industry && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md border border-slate-200 text-xs">
                {company.industry}
              </span>
            )}
            {(company.city || company.country) && (
              <>
                <span className="text-slate-300">·</span>
                <span className="inline-flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  {[company.city, company.country].filter(Boolean).join(', ')}
                </span>
              </>
            )}
            {company.size_range && (
              <>
                <span className="text-slate-300">·</span>
                <span>{company.size_range}</span>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <Button variant="secondary" size="sm" icon={Edit2} onClick={onEdit}>
            Modifier
          </Button>
          {canAudit && (
            <Button
              variant="secondary"
              size="sm"
              icon={Zap}
              onClick={onGenerateAudit}
              loading={isAuditBusy}
            >
              Audit Startup Radar
            </Button>
          )}
          <Button variant="primary" size="sm" icon={Plus} onClick={onNewDeal}>
            Opportunite
          </Button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-px bg-slate-200 rounded-xl overflow-hidden border border-slate-200">
        <Kpi
          icon={Star}
          label="Score"
          value={String(company.audit_score ?? '—')}
          suffix={company.audit_score ? '/ 100' : ''}
          trend={company.audit_score ? 'Auditee' : 'Non auditee'}
        />
        <Kpi
          icon={TrendingUp}
          label="Gagne"
          value={`${(kpi.wonAmount / 1000).toFixed(1)}`}
          suffix="k EUR"
          trend={kpi.wonAmount > 0 ? 'Cumul' : '—'}
        />
        <Kpi
          icon={Target}
          label="Pipeline"
          value={`${(kpi.pipeline / 1000).toFixed(1)}`}
          suffix="k EUR"
          trend={`${kpi.dealsCount} deal${kpi.dealsCount > 1 ? 's' : ''}`}
        />
        <Kpi
          icon={ActivityIcon}
          label="Activite 30j"
          value={String(activityCount)}
          trend={kpi.lastActivity ? formatRelative(kpi.lastActivity) : 'Aucune'}
        />
      </div>
    </div>
  );
}
