// =============================================================================
// FGA CRM - Board Kanban drag & drop (7 colonnes de stages)
// =============================================================================

import { DragDropContext, Droppable, type DropResult } from '@hello-pangea/dnd';
import { useMemo } from 'react';

import type { Deal } from '../../types';
import { DEAL_STAGES } from '../../types';
import KanbanCard from './KanbanCard';

const STAGE_COLORS: Record<string, string> = {
  new: 'border-slate-300',
  contacted: 'border-blue-300',
  meeting: 'border-indigo-300',
  proposal: 'border-amber-300',
  negotiation: 'border-orange-300',
  won: 'border-emerald-400',
  lost: 'border-red-300',
};

interface KanbanBoardProps {
  deals: Deal[];
  onStageChange: (dealId: string, newStage: string) => void;
  onDealClick: (deal: Deal) => void;
}

export default function KanbanBoard({ deals, onStageChange, onDealClick }: KanbanBoardProps) {
  // Grouper les deals par stage
  const columns = useMemo(() => {
    const map: Record<string, Deal[]> = {};
    for (const stage of DEAL_STAGES) {
      map[stage.value] = [];
    }
    for (const deal of deals) {
      if (map[deal.stage]) {
        map[deal.stage].push(deal);
      }
    }
    return map;
  }, [deals]);

  const handleDragEnd = (result: DropResult) => {
    const { destination, source, draggableId } = result;

    // Pas de destination ou meme colonne + meme position
    if (!destination) return;
    if (destination.droppableId === source.droppableId && destination.index === source.index) return;

    // Changement de stage
    if (destination.droppableId !== source.droppableId) {
      onStageChange(draggableId, destination.droppableId);
    }
  };

  const formatTotal = (deals: Deal[]) => {
    const total = deals.reduce((sum, d) => sum + (d.amount || 0), 0);
    if (total === 0) return null;
    return `${total.toLocaleString('fr-FR')} €`;
  };

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="flex gap-3 overflow-x-auto pb-4" style={{ minHeight: 500 }}>
        {DEAL_STAGES.map((stage) => {
          const stageDeals = columns[stage.value] || [];
          const totalAmount = formatTotal(stageDeals);

          return (
            <div
              key={stage.value}
              className={`flex-shrink-0 w-64 bg-slate-50 rounded-xl border-t-4 ${STAGE_COLORS[stage.value] || 'border-slate-300'}`}
            >
              {/* Header colonne */}
              <div className="p-3 pb-2">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-semibold text-slate-700">{stage.label}</h3>
                  <span className="text-xs font-medium text-slate-400 bg-white rounded-full px-2 py-0.5">
                    {stageDeals.length}
                  </span>
                </div>
                {totalAmount && (
                  <p className="text-xs text-slate-500">{totalAmount}</p>
                )}
              </div>

              {/* Liste droppable */}
              <Droppable droppableId={stage.value}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`
                      px-2 pb-2 min-h-[100px] transition-colors rounded-b-xl
                      ${snapshot.isDraggingOver ? 'bg-blue-50/60' : ''}
                    `}
                  >
                    {stageDeals.map((deal, index) => (
                      <KanbanCard
                        key={deal.id}
                        deal={deal}
                        index={index}
                        onClick={() => onDealClick(deal)}
                      />
                    ))}
                    {provided.placeholder}

                    {stageDeals.length === 0 && !snapshot.isDraggingOver && (
                      <p className="text-xs text-slate-300 text-center py-6">
                        Glisser un deal ici
                      </p>
                    )}
                  </div>
                )}
              </Droppable>
            </div>
          );
        })}
      </div>
    </DragDropContext>
  );
}
