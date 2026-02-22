// =============================================================================
// FGA CRM - Contacts Page
// =============================================================================

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Users, Plus, Search, RefreshCw } from 'lucide-react';
import { getContacts } from '../api/client';
import type { Contact } from '../types';

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-slate-100 text-slate-600',
  contacted: 'bg-blue-50 text-blue-700',
  qualified: 'bg-emerald-50 text-emerald-700',
  unqualified: 'bg-red-50 text-red-600',
  nurturing: 'bg-amber-50 text-amber-700',
};

export default function ContactsPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['contacts', { page, search }],
    queryFn: () => getContacts({ page, size: 25, search: search || undefined }),
  });

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Contacts</h1>
          <p className="text-slate-400 text-sm mt-1">{data?.total || 0} contacts au total</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2.5 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-colors">
          <Plus className="w-4 h-4" />
          Nouveau contact
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Rechercher un contact..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-400">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
            <p className="text-sm">Chargement...</p>
          </div>
        ) : !data?.items?.length ? (
          <div className="p-8 text-center text-slate-400">
            <Users className="w-6 h-6 mx-auto mb-2" />
            <p className="text-sm">Aucun contact trouvé</p>
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Nom</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Titre</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Statut</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((contact: Contact) => (
                  <tr key={contact.id} className="hover:bg-slate-50 cursor-pointer transition-colors">
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-slate-700">{contact.full_name}</p>
                      {contact.job_level && (
                        <p className="text-xs text-slate-400">{contact.job_level}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{contact.title || '—'}</td>
                    <td className="px-6 py-4 text-sm text-slate-500">{contact.email || '—'}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${STATUS_COLORS[contact.status] || STATUS_COLORS.new}`}>
                        {contact.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{contact.lead_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {data.pages > 1 && (
              <div className="px-6 py-3 border-t border-slate-100 flex items-center justify-between">
                <p className="text-xs text-slate-400">
                  Page {data.page} sur {data.pages}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 text-xs text-slate-500 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
                  >
                    Précédent
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                    disabled={page >= data.pages}
                    className="px-3 py-1.5 text-xs text-slate-500 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
                  >
                    Suivant
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
