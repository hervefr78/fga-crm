// =============================================================================
// FGA CRM - Dashboard Page
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import {
  Users,
  Building2,
  Target,
  ListTodo,
  RefreshCw,
  AlertCircle,
  TrendingUp,
} from 'lucide-react';
import clsx from 'clsx';
import { getContacts, getCompanies, getDeals, getHealth } from '../api/client';

interface StatCardProps {
  title: string;
  value: number;
  icon: React.ElementType;
  color: string;
  bgColor: string;
}

function StatCard({ title, value, icon: Icon, color, bgColor }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
      <div className="flex items-center gap-4">
        <div className={clsx('p-3 rounded-xl', bgColor)}>
          <Icon className={clsx('w-6 h-6', color)} />
        </div>
        <div>
          <p className="text-slate-400 text-sm">{title}</p>
          <p className="text-2xl font-bold text-slate-800 mt-0.5">
            {value.toLocaleString('fr-FR')}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  });

  const { data: contacts } = useQuery({
    queryKey: ['contacts', { size: 1 }],
    queryFn: () => getContacts({ size: 1 }),
  });

  const { data: companies } = useQuery({
    queryKey: ['companies', { size: 1 }],
    queryFn: () => getCompanies({ size: 1 }),
  });

  const { data: deals } = useQuery({
    queryKey: ['deals', { size: 5 }],
    queryFn: () => getDeals({ size: 5 }),
  });

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">Vue d'ensemble de votre activité commerciale</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <StatCard
          title="Contacts"
          value={contacts?.total || 0}
          icon={Users}
          color="text-blue-600"
          bgColor="bg-blue-50"
        />
        <StatCard
          title="Entreprises"
          value={companies?.total || 0}
          icon={Building2}
          color="text-emerald-600"
          bgColor="bg-emerald-50"
        />
        <StatCard
          title="Deals"
          value={deals?.total || 0}
          icon={Target}
          color="text-violet-600"
          bgColor="bg-violet-50"
        />
        <StatCard
          title="Tâches"
          value={0}
          icon={ListTodo}
          color="text-amber-600"
          bgColor="bg-amber-50"
        />
      </div>

      {/* Recent Deals */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-slate-400" />
            <h2 className="text-base font-semibold text-slate-800">Derniers deals</h2>
          </div>
          <a href="/pipeline" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
            Voir le pipeline →
          </a>
        </div>

        {!deals?.items?.length ? (
          <div className="p-8 text-center text-slate-400">
            <AlertCircle className="w-6 h-6 mx-auto mb-2" />
            <p className="text-sm">Aucun deal. Créez votre premier deal pour démarrer.</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Deal</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Stage</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Montant</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Probabilité</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {deals.items.map((deal) => (
                <tr key={deal.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <p className="text-sm font-medium text-slate-700">{deal.title}</p>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2.5 py-1 bg-primary-50 text-primary-700 text-xs font-medium rounded-full">
                      {deal.stage}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {deal.amount ? `${deal.amount.toLocaleString('fr-FR')} ${deal.currency}` : '—'}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-500">{deal.probability}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Status */}
      <div className="mt-4 text-xs text-slate-300 flex items-center gap-2">
        <span className={clsx('w-1.5 h-1.5 rounded-full', health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-red-400')} />
        {health?.app} v{health?.version} — {health?.status || 'disconnected'}
      </div>
    </div>
  );
}
