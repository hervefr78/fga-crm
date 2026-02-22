// =============================================================================
// FGA CRM - Dashboard V2 (graphiques + KPIs)
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import {
  Users,
  Building2,
  Target,
  TrendingUp,
  AlertCircle,
  Activity,
  Mail,
  Phone,
  Calendar,
  StickyNote,
  Linkedin,
  CheckSquare,
  Award,
  BarChart3,
  Send,
} from 'lucide-react';
import clsx from 'clsx';
import { getDeals, getActivities, getHealth, getDashboardStats } from '../api/client';
import type { DashboardStats } from '../types';
import KpiCard from '../components/dashboard/KpiCard';
import PipelineChart from '../components/dashboard/PipelineChart';
import ActivityChart from '../components/dashboard/ActivityChart';
import TaskProgress from '../components/dashboard/TaskProgress';

// Icones par type d'activite
const ACTIVITY_TYPE_ICONS: Record<string, React.ElementType> = {
  email: Mail,
  call: Phone,
  meeting: Calendar,
  note: StickyNote,
  linkedin: Linkedin,
  task: CheckSquare,
  audit: BarChart3,
};

const ACTIVITY_TYPE_LABELS: Record<string, string> = {
  email: 'Email',
  call: 'Appel',
  meeting: 'Meeting',
  note: 'Note',
  linkedin: 'LinkedIn',
  task: 'Tache',
  audit: 'Audit',
};

// Formatage montant EUR
function formatCurrency(amount: number): string {
  if (amount >= 1_000_000) {
    return `${(amount / 1_000_000).toFixed(1).replace('.0', '')} M\u00A0\u20AC`;
  }
  if (amount >= 1_000) {
    return `${(amount / 1_000).toFixed(0)} k\u00A0\u20AC`;
  }
  return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
}

export default function Dashboard() {
  // Stats agregees (1 seul appel API)
  const { data: stats } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  // Derniers deals (pour la liste)
  const { data: deals } = useQuery({
    queryKey: ['deals', { size: 5 }],
    queryFn: () => getDeals({ size: 5 }),
  });

  // Activites recentes (pour la liste)
  const { data: recentActivities } = useQuery({
    queryKey: ['activities', { size: 5 }],
    queryFn: () => getActivities({ size: 5 }),
  });

  // Health check
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  });

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Taux de conversion
  const totalClosedDeals = (stats?.deals_won_count || 0) + (stats?.deals_lost_count || 0);
  const conversionRate = totalClosedDeals > 0
    ? Math.round(((stats?.deals_won_count || 0) / totalClosedDeals) * 100)
    : 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">Vue d'ensemble de votre activite commerciale</p>
      </div>

      {/* KPI Cards — 5 colonnes */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
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
          title="Revenue"
          value={formatCurrency(stats?.deals_won_amount || 0)}
          subtitle={stats?.deals_won_count ? `${stats.deals_won_count} gagne${stats.deals_won_count > 1 ? 's' : ''}` : undefined}
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

      {/* Graphiques — Pipeline + Activites */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Pipeline par stage */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-slate-400" />
            <h2 className="text-base font-semibold text-slate-800">Pipeline par stage</h2>
          </div>
          <div className="px-4 py-4 h-64">
            <PipelineChart data={stats?.deals_by_stage || []} />
          </div>
        </div>

        {/* Activites par type */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-slate-400" />
              <h2 className="text-base font-semibold text-slate-800">Activites (30j)</h2>
            </div>
            <span className="text-sm text-slate-400">{stats?.activities_total_30d || 0} total</span>
          </div>
          <div className="px-4 py-4 h-64">
            <ActivityChart data={stats?.activities_by_type || []} />
          </div>
        </div>
      </div>

      {/* Taches + Emails */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Taches */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-5 h-5 text-slate-400" />
              <h2 className="text-base font-semibold text-slate-800">Taches</h2>
            </div>
            <a href="/tasks" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
              Voir tout →
            </a>
          </div>
          <TaskProgress
            total={stats?.tasks_total || 0}
            completed={stats?.tasks_completed || 0}
            overdue={stats?.tasks_overdue || 0}
          />
        </div>

        {/* Emails envoyes */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Send className="w-5 h-5 text-slate-400" />
              <h2 className="text-base font-semibold text-slate-800">Emails envoyes (30j)</h2>
            </div>
            <a href="/email" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
              Voir tout →
            </a>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-50 rounded-lg">
              <Mail className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-3xl font-bold text-slate-800">{stats?.emails_sent_30d || 0}</p>
              <p className="text-xs text-slate-400">emails envoyes</p>
            </div>
          </div>
        </div>
      </div>

      {/* Derniers deals + Activites recentes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Derniers deals */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-slate-400" />
              <h2 className="text-base font-semibold text-slate-800">Derniers deals</h2>
            </div>
            <a href="/pipeline" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
              Voir tout →
            </a>
          </div>

          {!deals?.items?.length ? (
            <div className="p-8 text-center text-slate-400">
              <AlertCircle className="w-6 h-6 mx-auto mb-2" />
              <p className="text-sm">Aucun deal pour le moment.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {deals.items.map((deal: { id: string; title: string; stage: string; amount: number | null; currency: string }) => (
                <div key={deal.id} className="px-6 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-700">{deal.title}</p>
                    <span className="px-2 py-0.5 bg-primary-50 text-primary-700 text-xs font-medium rounded-full">
                      {deal.stage}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500">
                    {deal.amount ? `${deal.amount.toLocaleString('fr-FR')} ${deal.currency}` : '—'}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Activites recentes */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-slate-400" />
              <h2 className="text-base font-semibold text-slate-800">Activites recentes</h2>
            </div>
            <a href="/activities" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
              Voir tout →
            </a>
          </div>

          {!recentActivities?.items?.length ? (
            <div className="p-8 text-center text-slate-400">
              <AlertCircle className="w-6 h-6 mx-auto mb-2" />
              <p className="text-sm">Aucune activite pour le moment.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {recentActivities.items.map((activity: { id: string; type: string; subject: string | null; created_at: string }) => {
                const Icon = ACTIVITY_TYPE_ICONS[activity.type] || Activity;
                return (
                  <div key={activity.id} className="px-6 py-3 flex items-center gap-3">
                    <Icon className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700">
                        <span className="font-medium">{ACTIVITY_TYPE_LABELS[activity.type] || activity.type}</span>
                        {activity.subject && <span className="text-slate-500"> — {activity.subject}</span>}
                      </p>
                    </div>
                    <span className="text-xs text-slate-400 flex-shrink-0">{formatDate(activity.created_at)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="text-xs text-slate-300 flex items-center gap-2">
        <span className={clsx('w-1.5 h-1.5 rounded-full', health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-red-400')} />
        {health?.app} v{health?.version} — {health?.status || 'disconnected'}
      </div>
    </div>
  );
}
