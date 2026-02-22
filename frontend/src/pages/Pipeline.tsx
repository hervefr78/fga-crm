// =============================================================================
// FGA CRM - Pipeline Page (liste deals + CRUD)
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Target, Plus, Trash2 } from 'lucide-react';

import { getDeals, deleteDeal } from '../api/client';
import type { Deal } from '../types';
import { Modal, SearchInput, Pagination, LoadingSpinner, EmptyState, ConfirmDialog, Badge, Button } from '../components/ui';
import DealForm from '../components/pipeline/DealForm';

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

export default function PipelinePage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingDeal, setEditingDeal] = useState<Deal | undefined>(undefined);
  const [deletingDeal, setDeletingDeal] = useState<Deal | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['deals', { page, search }],
    queryFn: () => getDeals({ page, size: 25, search: search || undefined }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteDeal(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['deals'] });
      setDeletingDeal(null);
    },
  });

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const openCreate = () => {
    setEditingDeal(undefined);
    setFormOpen(true);
  };

  const openEdit = (deal: Deal) => {
    setEditingDeal(deal);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingDeal(undefined);
  };

  const formatAmount = (amount: number | null, currency: string) => {
    if (amount === null) return '—';
    return `${amount.toLocaleString('fr-FR')} ${currency}`;
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Pipeline</h1>
          <p className="text-slate-400 text-sm mt-1">{data?.total || 0} deals</p>
        </div>
        <Button icon={Plus} onClick={openCreate}>
          Nouveau deal
        </Button>
      </div>

      {/* Recherche */}
      <div className="mb-5">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Rechercher un deal..."
        />
      </div>

      {/* Tableau */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.items?.length ? (
          <EmptyState icon={Target} message="Aucun deal trouvé" />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Deal</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Stage</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Montant</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Priorité</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Probabilité</th>
                  <th className="px-6 py-3 w-12" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((deal: Deal) => (
                  <tr
                    key={deal.id}
                    onClick={() => openEdit(deal)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-slate-700">{deal.title}</p>
                      {deal.expected_close_date && (
                        <p className="text-xs text-slate-400">Clôture : {deal.expected_close_date}</p>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={STAGE_VARIANTS[deal.stage] || 'default'}>
                        {STAGE_LABELS[deal.stage] || deal.stage}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">
                      {formatAmount(deal.amount, deal.currency)}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={PRIORITY_VARIANTS[deal.priority] || 'default'}>
                        {deal.priority}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{deal.probability}%</td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingDeal(deal);
                        }}
                        className="p-1 text-slate-300 hover:text-red-500 rounded transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPageChange={setPage}
            />
          </>
        )}
      </div>

      {/* Modal creation / edition */}
      <Modal
        open={formOpen}
        onClose={closeForm}
        title={editingDeal ? 'Modifier le deal' : 'Nouveau deal'}
        size="lg"
      >
        <DealForm
          deal={editingDeal}
          onSuccess={closeForm}
          onCancel={closeForm}
        />
      </Modal>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={!!deletingDeal}
        onClose={() => setDeletingDeal(null)}
        onConfirm={() => deletingDeal && deleteMutation.mutate(deletingDeal.id)}
        title="Supprimer le deal"
        message={`Voulez-vous vraiment supprimer « ${deletingDeal?.title} » ? Cette action est irréversible.`}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
