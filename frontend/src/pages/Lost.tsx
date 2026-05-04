// =============================================================================
// FGA CRM - Page "Deals perdus" (lost)
// =============================================================================

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { getDeals, getDealsStats } from '../api/client';
import type { Deal, DealsStats, PaginatedResponse } from '../types';
import { isManagerOrAbove } from '../types';
import { useAuth } from '../contexts/useAuth';
import { Pagination, LoadingSpinner, EmptyState } from '../components/ui';
import DealsTable from '../components/deals/DealsTable';
import DealsStatsBar from '../components/deals/DealsStatsBar';
import DealsFiltersBar from '../components/deals/DealsFiltersBar';
import type { DealsFilterValues } from '../components/deals/DealsFiltersBar';
import { lastDayOfMonth } from '../utils/format';

const PAGE_SIZE = 25;

const INITIAL_FILTERS: DealsFilterValues = {
  company_id: '',
  month: '',
  pricing_type: '',
  owner_id: '',
  search: '',
};

const LOST_COLUMNS = ['title', 'company', 'amount', 'actual_close_date', 'loss_reason', 'owner'] as const;

export default function LostPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [filters, setFilters] = useState<DealsFilterValues>(INITIAL_FILTERS);
  const [page, setPage] = useState(1);

  // Construire les filtres backend (cf Signed.tsx pour la logique)
  const queryParams = useMemo(() => {
    const params: Record<string, string> = {};

    if (filters.search) params.search = filters.search;
    if (filters.company_id) params.company_id = filters.company_id;
    if (filters.owner_id) params.owner_id = filters.owner_id;
    // pricing_type non affiche pour Lost mais on le laisse passer si jamais set

    if (filters.month) {
      const last = lastDayOfMonth(filters.month);
      if (last) {
        params.close_date_from = `${filters.month}-01`;
        params.close_date_to = last;
      }
    }

    return params;
  }, [filters]);

  const listQuery = useQuery<PaginatedResponse<Deal>>({
    queryKey: ['deals', 'lost', { ...queryParams, page }],
    queryFn: () => getDeals({ category: 'lost', ...queryParams, page, size: PAGE_SIZE }),
  });

  const statsQuery = useQuery<DealsStats>({
    queryKey: ['deals-stats', 'lost', queryParams],
    queryFn: () => getDealsStats({ category: 'lost', ...queryParams }),
  });

  const handleFilterChange = (key: keyof DealsFilterValues, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const goToDeal = (deal: Deal) => {
    navigate(`/pipeline/${deal.id}`);
  };

  const data = listQuery.data;
  const isLoading = listQuery.isLoading;
  const isError = listQuery.isError;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Deals perdus</h1>
        <p className="text-slate-400 text-sm mt-1">Analyse des opportunités non converties</p>
      </div>

      {/* KPIs (count + total uniquement, pas de MRR/ARR) */}
      <div className="mb-6">
        <DealsStatsBar stats={statsQuery.data} showRecurring={false} />
      </div>

      {/* Filtres (sans pricing_type) */}
      <div className="mb-5">
        <DealsFiltersBar
          values={filters}
          onChange={handleFilterChange}
          showOwner={isManagerOrAbove(user)}
          showPricingType={false}
        />
      </div>

      {/* Tableau */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <LoadingSpinner />
        ) : isError ? (
          <EmptyState icon={XCircle} message="Erreur de chargement des deals perdus." />
        ) : !data?.items?.length ? (
          <EmptyState icon={XCircle} message="Aucun deal perdu pour ces filtres." />
        ) : (
          <>
            <DealsTable
              deals={data.items}
              columns={[...LOST_COLUMNS]}
              onRowClick={goToDeal}
            />
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    </div>
  );
}
