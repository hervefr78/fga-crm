// =============================================================================
// FGA CRM - GEO : selecteur de marque recherchable + mini-score (extrait de GEO.tsx)
// =============================================================================

import { useEffect, useRef, useState } from 'react';
import { Check, ChevronsUpDown, Plus, Search } from 'lucide-react';
import clsx from 'clsx';

import type { GeoBrandOverview } from '../../types/geo';
import { formatRate } from './geoUtils';

export function BrandSelector({
  brands, fallbackName, activeBrandId, onSelect, canWrite, onAddBrand,
}: {
  brands: GeoBrandOverview[];
  fallbackName: string | null;
  activeBrandId: string | null;
  onSelect: (id: string) => void;
  canWrite: boolean;
  onAddBrand: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  // Fermeture au clic exterieur + touche Echap
  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const active = brands.find((b) => b.id === activeBrandId);
  const label = active?.name ?? fallbackName ?? 'Choisir une marque';
  const q = query.trim().toLowerCase();
  const filtered = q ? brands.filter((b) => b.name.toLowerCase().includes(q)) : brands;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 min-w-[220px] px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
      >
        <span className="font-medium text-slate-800 truncate">{label}</span>
        {active && (
          <span className="ml-auto text-xs tabular-nums text-slate-500">
            {formatRate(active.visibility_rate)}
          </span>
        )}
        <ChevronsUpDown className="w-4 h-4 text-slate-400 shrink-0" />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-72 rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-100">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher une marque..."
              className="w-full text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
            />
          </div>
          <ul className="max-h-64 overflow-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-slate-400">Aucune marque</li>
            ) : (
              filtered.map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => { onSelect(b.id); setOpen(false); setQuery(''); }}
                    className={clsx(
                      'w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-slate-50',
                      b.id === activeBrandId ? 'text-primary-700' : 'text-slate-700',
                    )}
                  >
                    {b.id === activeBrandId ? (
                      <Check className="w-3.5 h-3.5 text-primary-600 shrink-0" />
                    ) : (
                      <span className="w-3.5 shrink-0" />
                    )}
                    <span className="truncate">{b.name}</span>
                    <span className="ml-auto text-xs tabular-nums text-slate-500">
                      {formatRate(b.visibility_rate)}
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
          {canWrite && (
            <button
              type="button"
              onClick={() => { setOpen(false); onAddBrand(); }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-primary-700 border-t border-slate-100 hover:bg-slate-50"
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter une marque
            </button>
          )}
        </div>
      )}
    </div>
  );
}
