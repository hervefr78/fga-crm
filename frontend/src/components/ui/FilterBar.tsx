// =============================================================================
// FGA CRM - Barre de filtres reutilisable
// =============================================================================

import { RotateCcw } from 'lucide-react';
import clsx from 'clsx';

// ---------- Types ----------

export interface FilterDef {
  key: string;
  label: string;
  type: 'select' | 'date' | 'boolean';
  options?: { value: string; label: string }[];
}

interface FilterBarProps {
  filters: FilterDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
}

// ---------- Composant ----------

export default function FilterBar({ filters, values, onChange, onReset }: FilterBarProps) {
  const hasActiveFilters = Object.values(values).some((v) => v !== '');

  return (
    <div className="flex items-end gap-3 flex-wrap">
      {filters.map((filter) => (
        <div key={filter.key} className="min-w-[140px]">
          <label className="block text-xs font-medium text-slate-500 mb-1">
            {filter.label}
          </label>

          {filter.type === 'select' && filter.options && (
            <select
              value={values[filter.key] || ''}
              onChange={(e) => onChange(filter.key, e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
            >
              <option value="">Tous</option>
              {filter.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}

          {filter.type === 'boolean' && (
            <select
              value={values[filter.key] || ''}
              onChange={(e) => onChange(filter.key, e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
            >
              <option value="">Tous</option>
              <option value="true">Oui</option>
              <option value="false">Non</option>
            </select>
          )}

          {filter.type === 'date' && (
            <input
              type="date"
              value={values[filter.key] || ''}
              onChange={(e) => onChange(filter.key, e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
            />
          )}
        </div>
      ))}

      {hasActiveFilters && (
        <button
          onClick={onReset}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors',
            'text-slate-600 hover:text-slate-800 hover:bg-slate-100',
          )}
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Réinitialiser
        </button>
      )}
    </div>
  );
}
