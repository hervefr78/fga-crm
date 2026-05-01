// =============================================================================
// FGA CRM - Bar de KPI pour les vues Signed / Lost
// =============================================================================

import { Activity, Target, TrendingUp, Award } from 'lucide-react';
import KpiCard from '../dashboard/KpiCard';
import type { DealsStats } from '../../types';
import { formatCurrency } from '../../utils/format';

interface DealsStatsBarProps {
  stats: DealsStats | undefined;
  // Si false : afficher uniquement count + total (vue Lost)
  showRecurring?: boolean;
}

export default function DealsStatsBar({ stats, showRecurring = true }: DealsStatsBarProps) {
  // Defaults safes (DC2 — afficher 0 plutot qu'un undefined visible)
  const count = stats?.count ?? 0;
  const totalAmount = stats?.total_amount ?? 0;
  const mrr = stats?.mrr ?? 0;
  const arr = stats?.arr ?? 0;

  if (!showRecurring) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <KpiCard
          title="Nombre de deals"
          value={count.toLocaleString('fr-FR')}
          icon={Target}
          color="text-violet-600"
          bgColor="bg-violet-50"
        />
        <KpiCard
          title="Montant total"
          value={formatCurrency(totalAmount)}
          icon={TrendingUp}
          color="text-slate-600"
          bgColor="bg-slate-50"
        />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        title="Nombre de deals"
        value={count.toLocaleString('fr-FR')}
        icon={Award}
        color="text-emerald-600"
        bgColor="bg-emerald-50"
      />
      <KpiCard
        title="Revenus totaux"
        value={formatCurrency(totalAmount)}
        icon={TrendingUp}
        color="text-emerald-600"
        bgColor="bg-emerald-50"
      />
      <KpiCard
        title="MRR"
        value={formatCurrency(mrr)}
        subtitle="Revenus mensuels récurrents"
        icon={Activity}
        color="text-indigo-600"
        bgColor="bg-indigo-50"
      />
      <KpiCard
        title="ARR"
        value={formatCurrency(arr)}
        subtitle="Annual Recurring Revenue"
        icon={TrendingUp}
        color="text-indigo-600"
        bgColor="bg-indigo-50"
      />
    </div>
  );
}
