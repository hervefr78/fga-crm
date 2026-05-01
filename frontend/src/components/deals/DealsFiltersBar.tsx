// =============================================================================
// FGA CRM - Barre de filtres pour les vues Signed / Lost
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { getCompanies, getUsersLookup } from '../../api/client';
import { DEAL_PRICING_TYPES } from '../../types';
import type { Company, UserLookup, PaginatedResponse } from '../../types';

// ---------- Types ----------

export interface DealsFilterValues {
  company_id: string;
  // Format YYYY-MM (mois de cloture). La page parent calcule from/to.
  month: string;
  pricing_type: string;
  owner_id: string;
  search: string;
}

interface DealsFiltersBarProps {
  values: DealsFilterValues;
  onChange: (key: keyof DealsFilterValues, value: string) => void;
  // Active le chargement de la liste des owners. En pratique on l'active pour
  // les manager+ via la page parent (les sales recoivent uniquement leur propre
  // user et le filtre est alors masque automatiquement — voir users.length > 1).
  showOwner?: boolean;
  // Lost ne propose pas de pricing (peu utile en analyse de perte)
  showPricingType?: boolean;
}

// ---------- Composant ----------

export default function DealsFiltersBar({
  values,
  onChange,
  showOwner = false,
  showPricingType = true,
}: DealsFiltersBarProps) {
  // Charger les entreprises (max 200 pour rester raisonnable — DC1)
  const { data: companies } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 200, forFilter: true }],
    queryFn: () => getCompanies({ size: 200 }),
  });

  // Lookup users (id + full_name) — accessible managers/admins.
  // Pour un sales, le backend retourne uniquement son propre user → le filtre
  // est alors masque (length <= 1) car non significatif.
  const { data: users } = useQuery<UserLookup[]>({
    queryKey: ['users-lookup'],
    queryFn: () => getUsersLookup(),
    enabled: showOwner,
    retry: false,
  });

  // Afficher le dropdown owner uniquement s'il y a au moins 2 users a filtrer.
  const hasOwnerFilter = !!users && users.length > 1;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
      {/* Search */}
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Recherche</label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={values.search}
            onChange={(e) => onChange('search', e.target.value)}
            placeholder="Titre du deal..."
            className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
          />
        </div>
      </div>

      {/* Company */}
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Entreprise</label>
        <select
          value={values.company_id}
          onChange={(e) => onChange('company_id', e.target.value)}
          className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
        >
          <option value="">Toutes</option>
          {companies?.items?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {/* Month picker */}
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Mois de clôture</label>
        <input
          type="month"
          value={values.month}
          onChange={(e) => onChange('month', e.target.value)}
          className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
        />
      </div>

      {/* Pricing type */}
      {showPricingType && (
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tarification</label>
          <select
            value={values.pricing_type}
            onChange={(e) => onChange('pricing_type', e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
          >
            <option value="">Toutes</option>
            {DEAL_PRICING_TYPES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Owner — visible si manager+ ET liste contient >= 2 users */}
      {showOwner && hasOwnerFilter && (
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Owner</label>
          <select
            value={values.owner_id}
            onChange={(e) => onChange('owner_id', e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
          >
            <option value="">Tous</option>
            {users?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
