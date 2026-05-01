// =============================================================================
// FGA CRM - Tableau de deals parametrable (Pipeline / Signed / Lost)
// =============================================================================

import { Trash2 } from 'lucide-react';
import { Badge } from '../ui';
import type { Deal } from '../../types';
import { DEAL_PRICING_TYPES, PRICING_PERIOD_MONTHS } from '../../types';
import { formatDateFR } from '../../utils/format';

// ---------- Types ----------

export type DealColumn =
  | 'title'
  | 'company'
  | 'stage'
  | 'amount'
  | 'mrr'
  | 'pricing_type'
  | 'priority'
  | 'probability'
  | 'expected_close_date'
  | 'actual_close_date'
  | 'loss_reason'
  | 'owner';

interface DealsTableProps {
  deals: Deal[];
  columns: DealColumn[];
  onRowClick?: (deal: Deal) => void;
  onDelete?: (deal: Deal) => void;
}

// ---------- Maps de presentation (DC8 — partagees) ----------

const STAGE_VARIANTS: Record<string, 'default' | 'info' | 'success' | 'danger' | 'warning'> = {
  new: 'default',
  contacted: 'info',
  meeting: 'info',
  proposal: 'warning',
  negotiation: 'warning',
  won: 'success',
  lost: 'danger',
};

const STAGE_LABELS: Record<string, string> = {
  new: 'Nouveau',
  contacted: 'Contacté',
  meeting: 'Meeting',
  proposal: 'Proposition',
  negotiation: 'Négociation',
  won: 'Gagné',
  lost: 'Perdu',
};

const PRIORITY_VARIANTS: Record<string, 'default' | 'info' | 'warning' | 'danger'> = {
  low: 'default',
  medium: 'info',
  high: 'warning',
  urgent: 'danger',
};

const PRICING_LABELS: Record<string, string> = Object.fromEntries(
  DEAL_PRICING_TYPES.map((p) => [p.value, p.label]),
);

const COLUMN_HEADERS: Record<DealColumn, string> = {
  title: 'Deal',
  company: 'Entreprise',
  stage: 'Stage',
  amount: 'Montant',
  mrr: 'MRR',
  pricing_type: 'Tarification',
  priority: 'Priorité',
  probability: 'Probabilité',
  expected_close_date: 'Clôture prévue',
  actual_close_date: 'Clôture',
  loss_reason: 'Raison',
  owner: 'Owner',
};

// ---------- Helpers de formatage par colonne ----------

const TRUNCATE_LIMIT = 60;

function truncate(text: string | null | undefined): string {
  if (!text) return '—';
  return text.length > TRUNCATE_LIMIT ? `${text.slice(0, TRUNCATE_LIMIT)}…` : text;
}

function formatAmount(amount: number | null, currency: string): string {
  if (amount === null || amount === undefined) return '—';
  // Affichage detaille (sans abreviation k/M) pour rester lisible dans une table
  return `${amount.toLocaleString('fr-FR')} ${currency}`;
}

function formatMrr(deal: Deal): string {
  if (deal.pricing_type === 'one_shot' || deal.recurring_amount === null || deal.recurring_amount === undefined) {
    return '—';
  }
  const months = PRICING_PERIOD_MONTHS[deal.pricing_type];
  if (!months) return '—';
  const mrr = deal.recurring_amount / months;
  return `${mrr.toFixed(0)} €/mois`;
}

// Render d'une cellule selon la colonne demandee
function renderCell(deal: Deal, column: DealColumn): React.ReactNode {
  switch (column) {
    case 'title':
      return (
        <div>
          <p className="text-sm font-medium text-slate-700">{deal.title}</p>
          {deal.expected_close_date && (
            <p className="text-xs text-slate-400">Prévu : {formatDateFR(deal.expected_close_date)}</p>
          )}
        </div>
      );
    case 'company':
      return <span className="text-sm text-slate-600">{deal.company_name || '—'}</span>;
    case 'stage':
      return (
        <Badge variant={STAGE_VARIANTS[deal.stage] || 'default'}>
          {STAGE_LABELS[deal.stage] || deal.stage}
        </Badge>
      );
    case 'amount':
      return <span className="text-sm text-slate-500">{formatAmount(deal.amount, deal.currency)}</span>;
    case 'mrr':
      return <span className="text-sm text-slate-500">{formatMrr(deal)}</span>;
    case 'pricing_type':
      return <span className="text-sm text-slate-500">{PRICING_LABELS[deal.pricing_type] || deal.pricing_type}</span>;
    case 'priority':
      return (
        <Badge variant={PRIORITY_VARIANTS[deal.priority] || 'default'}>
          {deal.priority}
        </Badge>
      );
    case 'probability':
      return <span className="text-sm text-slate-500">{deal.probability}%</span>;
    case 'expected_close_date':
      return <span className="text-sm text-slate-500">{formatDateFR(deal.expected_close_date)}</span>;
    case 'actual_close_date':
      return <span className="text-sm text-slate-500">{formatDateFR(deal.actual_close_date)}</span>;
    case 'loss_reason':
      return <span className="text-sm text-slate-500">{truncate(deal.loss_reason)}</span>;
    case 'owner':
      return <span className="text-sm text-slate-500">{deal.owner_name || '—'}</span>;
    default: {
      // Garde-fou DC5 — tous les cases doivent etre couverts
      const exhaustive: never = column;
      return exhaustive;
    }
  }
}

// ---------- Composant ----------

export default function DealsTable({ deals, columns, onRowClick, onDelete }: DealsTableProps) {
  return (
    <table className="w-full">
      <thead className="bg-slate-50">
        <tr>
          {columns.map((col) => (
            <th
              key={col}
              className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide"
            >
              {COLUMN_HEADERS[col]}
            </th>
          ))}
          {onDelete && <th className="px-6 py-3 w-12" />}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {deals.map((deal) => (
          <tr
            key={deal.id}
            onClick={() => onRowClick?.(deal)}
            className={onRowClick ? 'hover:bg-slate-50 cursor-pointer transition-colors' : ''}
          >
            {columns.map((col) => (
              <td key={col} className="px-6 py-4">
                {renderCell(deal, col)}
              </td>
            ))}
            {onDelete && (
              <td className="px-6 py-4">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(deal);
                  }}
                  aria-label={`Supprimer ${deal.title}`}
                  className="p-1 text-slate-300 hover:text-red-500 rounded transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
