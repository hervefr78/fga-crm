// =============================================================================
// FGA CRM - Page "Deals signes" (won)
// =============================================================================

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Award } from 'lucide-react';

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

const SIGNED_COLUMNS = ['title', 'company', 'pricing_type', 'amount', 'mrr', 'actual_close_date', 'owner'] as const;

export default function SignedPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [filters, setFilters] = useState<DealsFilterValues>(INITIAL_FILTERS);
  const [page, setPage] = useState(1);

  // Construire les filtres backend a partir du state local
  // - month "YYYY-MM" est expanded en close_date_from / close_date_to
  // - les valeurs vides sont retirees (undefined → axios skip le param)
  const queryParams = useMemo(() => {
    const params: Record<string, string> = {};

    if (filters.search) params.search = filters.search;
    if (filters.company_id) params.company_id = filters.company_id;
    if (filters.pricing_type) params.pricing_type = filters.pricing_type;
    if (filters.owner_id) params.owner_id = filters.owner_id;

    if (filters.month) {
      const last = lastDayOfMonth(filters.month);
      if (last) {
        params.close_date_from = `${filters.month}-01`;
        params.close_date_to = last;
      }
    }

    return params;
  }, [filters]);

  // Liste paginee
  const listQuery = useQuery<PaginatedResponse<Deal>>({
    queryKey: ['deals', 'signed', { ...queryParams, page }],
    queryFn: () => getDeals({ category: 'signed', ...queryParams, page, size: PAGE_SIZE }),
  });

  // Stats agregees (memes filtres, sans pagination)
  const statsQuery = useQuery<DealsStats>({
    queryKey: ['deals-stats', 'signed', queryParams],
    queryFn: () => getDealsStats({ category: 'signed', ...queryParams }),
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
        <h1 className="text-2xl font-bold text-slate-800">Deals signés</h1>
        <p className="text-slate-400 text-sm mt-1">Contrats gagnés et revenus consolidés</p>
      </div>

      {/* KPIs */}
      <div className="mb-6">
        <DealsStatsBar stats={statsQuery.data} showRecurring />
      </div>

      {/* Filtres */}
      <div className="mb-5">
        <DealsFiltersBar
          values={filters}
          onChange={handleFilterChange}
          showOwner={isManagerOrAbove(user)}
          showPricingType
        />
      </div>

      {/* Tableau */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <LoadingSpinner />
        ) : isError ? (
          <EmptyState icon={Award} message="Erreur de chargement des deals signés." />
        ) : !data?.items?.length ? (
          <EmptyState icon={Award} message="Aucun deal signé pour ces filtres." />
        ) : (
          <>
            <DealsTable
              deals={data.items}
              columns={[...SIGNED_COLUMNS]}
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
