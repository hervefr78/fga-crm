// =============================================================================
// FGA CRM - Company : cartes de la colonne principale (fiche detail)
// =============================================================================
// Colonne gauche de la grille "cartes | side" : AiCard (next best action),
// banniere audit SR, cartes "A propos" et "Derniere levee". Les onglets +
// contenu sont dans CompanyTabsSection (section pleine largeur, sous la grille).
// Purement presentationnel : queries & mutations restent dans la page.
// =============================================================================

import { TrendingUp, FileText, Edit2 } from 'lucide-react';

import type {
  Company, NextActionResponse, NextActionAction,
  AuditGenerateStatus, CompanyAuditResponse,
} from '../../types';
import { Badge } from '../ui';
import AiCard from '../ai/AiCard';
import { formatAmountMillions, formatDateFR } from '../../utils/format';
import { Card } from './CompanyAtoms';
import CompanyAuditBanner from './CompanyAuditBanner';

interface CompanyMainColumnProps {
  // AiCard (next best action)
  nextAction: NextActionResponse | null | undefined;
  nextActionLoading: boolean;
  onAiAction: (action: NextActionAction) => void;
  // Banniere de statut generation/import d'audit SR
  isGeneratingAudit: boolean;
  auditGenStatus: AuditGenerateStatus | undefined;
  importSuccess: boolean;
  importResult: CompanyAuditResponse | undefined;
  importError: boolean;
  importErrorMessage?: string;
  // Cartes "A propos" / "Derniere levee"
  company: Company;
  onEditDescription: () => void;
}

export default function CompanyMainColumn({
  nextAction,
  nextActionLoading,
  onAiAction,
  isGeneratingAudit,
  auditGenStatus,
  importSuccess,
  importResult,
  importError,
  importErrorMessage,
  company,
  onEditDescription,
}: CompanyMainColumnProps) {
  return (
    <div className="min-w-0 flex flex-col gap-4">

      {/* AI suggestion (branchee sur l'API reelle) */}
      <AiCard
        data={nextAction}
        loading={nextActionLoading}
        onAction={onAiAction}
      />

      {/* Statut generation / import d'audit SR (banniere) */}
      <CompanyAuditBanner
        isGeneratingAudit={isGeneratingAudit}
        auditGenStatus={auditGenStatus}
        importSuccess={importSuccess}
        importResult={importResult}
        importError={importError}
        importErrorMessage={importErrorMessage}
      />

      {/* Description */}
      {company.description && (
        <Card title="A propos" icon={FileText} action={
          <button
            onClick={onEditDescription}
            className="p-1 rounded hover:bg-slate-100"
            aria-label="Modifier la description"
          >
            <Edit2 className="w-3.5 h-3.5 text-slate-400" />
          </button>
        }>
          <p className="text-sm text-slate-700 leading-relaxed text-pretty">
            {company.description}
          </p>
        </Card>
      )}

      {/* Funding (synced from Startup Radar multi-source pipeline).
          Boolean() evite d'afficher un "0" litteral quand funding_amount === 0
          (en JSX, `{0 && ...}` rend le nombre 0). */}
      {Boolean(company.funding_date || company.funding_amount) && (
        <Card title="Derniere levee detectee" icon={TrendingUp}>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            {!!company.funding_amount && (
              <Badge variant="success">
                {formatAmountMillions(company.funding_amount)}
              </Badge>
            )}
            {company.funding_series && (
              <Badge variant="info">{company.funding_series}</Badge>
            )}
            {company.funding_date && (
              <span className="text-xs text-slate-500">
                {formatDateFR(company.funding_date)}
              </span>
            )}
          </div>
          {company.funding_sources && company.funding_sources.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              <span className="text-[11px] uppercase tracking-wider font-medium text-slate-400 mr-1">
                Sources
              </span>
              {company.funding_sources.map((src: string) => (
                <Badge key={src} variant="default" className="text-[10px] py-0.5">
                  {src}
                </Badge>
              ))}
            </div>
          )}
          {company.siren && (
            <p className="text-[11px] text-slate-400 mt-2 font-mono">
              SIREN : {company.siren}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
