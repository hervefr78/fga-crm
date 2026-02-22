// =============================================================================
// FGA CRM - Carte deal draggable pour le Kanban
// =============================================================================

import { Draggable } from '@hello-pangea/dnd';
import { Calendar } from 'lucide-react';

import type { Deal } from '../../types';
import { Badge } from '../ui';

const PRIORITY_VARIANTS: Record<string, 'default' | 'info' | 'warning' | 'danger'> = {
  low: 'default',
  medium: 'info',
  high: 'warning',
  urgent: 'danger',
};

interface KanbanCardProps {
  deal: Deal;
  index: number;
  onClick: () => void;
}

const formatAmount = (amount: number | null, currency: string) => {
  if (amount === null) return null;
  return `${amount.toLocaleString('fr-FR')} ${currency}`;
};

export default function KanbanCard({ deal, index, onClick }: KanbanCardProps) {
  return (
    <Draggable draggableId={deal.id} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          onClick={onClick}
          className={`
            bg-white rounded-lg border border-slate-200 p-3 mb-2 cursor-pointer
            transition-shadow hover:shadow-md
            ${snapshot.isDragging ? 'shadow-lg ring-2 ring-blue-200' : ''}
          `}
        >
          {/* Titre */}
          <p className="text-sm font-medium text-slate-700 mb-1 truncate">
            {deal.title}
          </p>

          {/* Montant */}
          {deal.amount !== null && (
            <p className="text-sm font-semibold text-slate-800 mb-2">
              {formatAmount(deal.amount, deal.currency)}
            </p>
          )}

          {/* Footer : priorite + date */}
          <div className="flex items-center justify-between">
            <Badge variant={PRIORITY_VARIANTS[deal.priority] || 'default'}>
              {deal.priority}
            </Badge>

            {deal.expected_close_date && (
              <span className="flex items-center gap-1 text-xs text-slate-400">
                <Calendar className="w-3 h-3" />
                {new Date(deal.expected_close_date).toLocaleDateString('fr-FR', {
                  day: '2-digit',
                  month: 'short',
                })}
              </span>
            )}
          </div>
        </div>
      )}
    </Draggable>
  );
}
