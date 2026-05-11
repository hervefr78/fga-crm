// =============================================================================
// FGA CRM - Dashboard (refonte UI conformement a UI_GUIDELINES §3.2 D)
// =============================================================================
//
// Layout :
//   [ Header simple : H1 + sous-titre ]
//   [ KPI strip principal (5 col) ]
//   [ Sous-strip recurrent (3 col) ]
//   [ AI card pleine largeur — /dashboard/next-actions ]
//   [ Grid 2/3 + 1/3 :
//       Main  -> charts (2 col) + timeline activites groupee
//       Side  -> taches en retard + emails 30j + derniers deals
//   ]
//   [ Footer status slim ]
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Users, Building2, Target, TrendingUp, Activity, Award,
  BarChart3, Mail, AlertCircle,
} from 'lucide-react';
import clsx from 'clsx';

import {
  getDeals, getActivities, getHealth, getDashboardStats, getTasks,
  getDashboardNextActions,
} from '../api/client';
import type {
  DashboardStats, NextActionResponse, Activity as ActivityType,
  Deal, Task, PaginatedResponse,
} from '../types';
import { formatCurrency } from '../utils/format';

import KpiCard from '../components/dashboard/KpiCard';
import PipelineChart from '../components/dashboard/PipelineChart';
import ActivityChart from '../components/dashboard/ActivityChart';
import DashboardTaskCard from '../components/dashboard/DashboardTaskCard';
import AiCard from '../components/ai/AiCard';
import TimelineGrouped from '../components/activities/TimelineGrouped';

// Bornes (DC1 — limites client-side explicites)
const TIMELINE_SIZE = 30;
const SIDE_DEAL_SIZE = 5;
const OVERDUE_TASK_SIZE = 5;

export default function Dashboard() {
  // Stats agregees (1 seul appel API)
  const { data: stats } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  // Suggestions IA hebdomadaires.
  // DC7 : retry: false pour ne pas spammer si endpoint pas encore deploye —
  // le client renvoie [] sur 404 (cf api/client.ts).
  const { data: suggestions = [], isLoading: suggestionsLoading } = useQuery<NextActionResponse[]>({
    queryKey: ['dashboard-next-actions'],
    queryFn: getDashboardNextActions,
    retry: false,
  });

  // 30 dernieres activites pour la timeline groupee
  const { data: activitiesPage } = useQuery<PaginatedResponse<ActivityType>>({
    queryKey: ['activities', { size: TIMELINE_SIZE }],
    queryFn: () => getActivities({ size: TIMELINE_SIZE }),
  });

  // Taches en retard pour la sidebar
  const { data: overdueTasksPage, isLoading: overdueTasksLoading } = useQuery<PaginatedResponse<Task>>({
    queryKey: ['tasks', { overdue: 'true', size: OVERDUE_TASK_SIZE }],
    queryFn: () => getTasks({ overdue: 'true', size: OVERDUE_TASK_SIZE }),
  });

  // Derniers deals pour la sidebar
  const { data: recentDealsPage } = useQuery<PaginatedResponse<Deal>>({
    queryKey: ['deals', { size: SIDE_DEAL_SIZE }],
    queryFn: () => getDeals({ size: SIDE_DEAL_SIZE }),
  });

  // Health check
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  });

  const activities: ActivityType[] = activitiesPage?.items ?? [];
  const overdueTasks: Task[] = overdueTasksPage?.items ?? [];
  const recentDeals: Deal[] = recentDealsPage?.items ?? [];

  // Taux de conversion (won / (won + lost))
  const totalClosedDeals = (stats?.deals_won_count || 0) + (stats?.deals_lost_count || 0);
  const conversionRate = totalClosedDeals > 0
    ? Math.round(((stats?.deals_won_count || 0) / totalClosedDeals) * 100)
    : 0;

  return (
    <div className="px-8 py-7 space-y-6">

      {/* ===== Header ===== */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-800">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">
          Vue d'ensemble de votre activite commerciale
        </p>
      </div>

      {/* ===== KPI strip principal — 5 colonnes ===== */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <KpiCard
          title="Contacts"
          value={(stats?.contacts_total || 0).toLocaleString('fr-FR')}
          subtitle={stats?.contacts_this_month ? `+${stats.contacts_this_month} ce mois` : undefined}
          icon={Users}
          color="text-blue-600"
          bgColor="bg-blue-50"
        />
        <KpiCard
          title="Entreprises"
          value={(stats?.companies_total || 0).toLocaleString('fr-FR')}
          icon={Building2}
          color="text-emerald-600"
          bgColor="bg-emerald-50"
        />
        <KpiCard
          title="Pipeline"
          value={formatCurrency(stats?.deals_pipeline_amount || 0)}
          subtitle={`${stats?.deals_total || 0} deals`}
          icon={Target}
          color="text-violet-600"
          bgColor="bg-violet-50"
        />
        <KpiCard
          title="Revenue one-shot"
          value={formatCurrency(stats?.deals_one_shot_won || 0)}
          subtitle="Contrats ponctuels gagnes"
          icon={TrendingUp}
          color="text-emerald-600"
          bgColor="bg-emerald-50"
        />
        <KpiCard
          title="Conversion"
          value={`${conversionRate}%`}
          subtitle={totalClosedDeals > 0 ? `${stats?.deals_won_count}w / ${totalClosedDeals} clos` : undefined}
          icon={Award}
          color="text-amber-600"
          bgColor="bg-amber-50"
        />
      </div>

      {/* ===== Sous-strip recurrent — 4 colonnes ===== */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="MRR actif"
          value={formatCurrency(stats?.deals_mrr_won || 0)}
          subtitle="Revenus mensuels recurrents (gagnes)"
          icon={Activity}
          color="text-indigo-600"
          bgColor="bg-indigo-50"
        />
        <KpiCard
          title="ARR"
          value={formatCurrency(stats?.deals_arr_won || 0)}
          subtitle="Annual Recurring Revenue"
          icon={TrendingUp}
          color="text-indigo-600"
          bgColor="bg-indigo-50"
        />
        <KpiCard
          title="MRR pipeline"
          value={formatCurrency(stats?.deals_mrr_pipeline || 0)}
          subtitle="MRR potentiel (deals ouverts)"
          icon={Target}
          color="text-violet-600"
          bgColor="bg-violet-50"
        />
        <KpiCard
          title="Levees 7j"
          value={String(stats?.recent_funding_count ?? 0)}
          subtitle={
            stats?.recent_funding_amount && stats.recent_funding_amount > 0
              ? formatCurrency(stats.recent_funding_amount)
              : 'Detectees par Startup Radar'
          }
          icon={TrendingUp}
          color="text-emerald-600"
          bgColor="bg-emerald-50"
        />
      </div>

      {/* ===== AI Card pleine largeur ===== */}
      {/* AiCard retourne null si suggestions === [] : pas de chrome vide (UI_GUIDELINES §1.4) */}
      <AiCard data={suggestions} loading={suggestionsLoading} />

      {/* ===== Grid 2/3 main + 1/3 side ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Colonne main — 2/3 */}
        <div className="lg:col-span-2 space-y-6">

          {/* Charts grid 2 colonnes */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Pipeline par stage */}
            <ChartCard title="Pipeline par stage" icon={BarChart3}>
              <div className="px-4 py-4 h-64">
                <PipelineChart data={stats?.deals_by_stage || []} />
              </div>
            </ChartCard>

            {/* Activites par type */}
            <ChartCard
              title="Activites (30j)"
              icon={Activity}
              right={
                <span className="text-xs text-slate-400 tabular-nums">
                  {stats?.activities_total_30d || 0} total
                </span>
              }
            >
              <div className="px-4 py-4 h-64">
                <ActivityChart data={stats?.activities_by_type || []} />
              </div>
            </ChartCard>
          </div>

          {/* Timeline activites groupee */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <Activity className="w-3.5 h-3.5 text-slate-400" />
                Activites recentes
                <span className="text-xs text-slate-400 tabular-nums font-normal">
                  · {activities.length}
                </span>
              </div>
              <Link
                to="/activities"
                className="text-xs text-primary-600 hover:text-primary-700 font-medium"
              >
                Voir tout →
              </Link>
            </div>
            <TimelineGrouped activities={activities} maxHeight="max-h-96" />
          </div>
        </div>

        {/* Colonne side — 1/3 */}
        <div className="space-y-6">

          {/* Taches en retard */}
          <DashboardTaskCard tasks={overdueTasks} loading={overdueTasksLoading} />

          {/* Emails envoyes 30j (compact) */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                Emails envoyes (30j)
              </div>
              <Link
                to="/email"
                className="text-xs text-primary-600 hover:text-primary-700 font-medium"
              >
                Voir tout →
              </Link>
            </div>
            <div className="p-4 flex items-baseline gap-2">
              <span className="text-2xl font-semibold text-slate-800 tabular-nums tracking-tight">
                {(stats?.emails_sent_30d || 0).toLocaleString('fr-FR')}
              </span>
              <span className="text-xs text-slate-500">emails</span>
            </div>
          </div>

          {/* Derniers deals */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
                Derniers deals
              </div>
              <Link
                to="/pipeline"
                className="text-xs text-primary-600 hover:text-primary-700 font-medium"
              >
                Voir tout →
              </Link>
            </div>
            {recentDeals.length === 0 ? (
              <div className="py-8 flex flex-col items-center justify-center text-center text-sm text-slate-400 gap-2 px-4">
                <div className="w-9 h-9 rounded-lg bg-slate-50 flex items-center justify-center">
                  <AlertCircle className="w-4 h-4" />
                </div>
                Aucun deal pour le moment
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {recentDeals.map((deal) => (
                  <li key={deal.id}>
                    <Link
                      to={`/pipeline/${deal.id}`}
                      className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-slate-50/60 transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-slate-800 truncate">
                          {deal.title}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          {deal.stage}
                        </div>
                      </div>
                      <div className="text-sm text-slate-700 tabular-nums whitespace-nowrap">
                        {deal.amount
                          ? `${deal.amount.toLocaleString('fr-FR')} ${deal.currency}`
                          : '—'}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* ===== Footer status (slim) ===== */}
      <div className="text-xs text-slate-400 flex items-center gap-2 pt-2">
        <span
          className={clsx(
            'w-1.5 h-1.5 rounded-full',
            health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-red-400',
          )}
        />
        {health?.app} v{health?.version} — {health?.status || 'disconnected'}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Sous-composants
// -----------------------------------------------------------------------------

// Wrapper de carte pour les charts (header avec icone slate-400 + titre + slot droit)
function ChartCard({
  title, icon: Icon, right, children,
}: {
  title: string;
  icon: React.ElementType;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          <Icon className="w-3.5 h-3.5 text-slate-400" />
          {title}
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}
