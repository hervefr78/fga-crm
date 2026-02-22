// =============================================================================
// FGA CRM - Recherche globale (header)
// =============================================================================

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, User, Building2, Handshake } from 'lucide-react';
import clsx from 'clsx';

import { globalSearch } from '../../api/client';
import { useDebounce } from '../../hooks/useDebounce';
import type { GlobalSearchResponse, SearchResultItem } from '../../types';

// ---------- Constantes ----------

const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 300;

const ENTITY_CONFIG = [
  { key: 'contacts' as const, label: 'Contacts', icon: User, route: '/contacts' },
  { key: 'companies' as const, label: 'Entreprises', icon: Building2, route: '/companies' },
  { key: 'deals' as const, label: 'Deals', icon: Handshake, route: '/deals' },
];

// ---------- Composant ----------

export default function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const debouncedQuery = useDebounce(query, DEBOUNCE_MS);

  const { data } = useQuery<GlobalSearchResponse>({
    queryKey: ['globalSearch', debouncedQuery],
    queryFn: () => globalSearch(debouncedQuery),
    enabled: debouncedQuery.length >= MIN_QUERY_LENGTH,
  });

  const hasResults = data && (
    data.contacts.length > 0 || data.companies.length > 0 || data.deals.length > 0
  );

  // Ouvrir le dropdown quand on a des resultats
  useEffect(() => {
    if (hasResults) setIsOpen(true);
  }, [hasResults]);

  // Fermer sur clic exterieur
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fermer sur Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setIsOpen(false);
        inputRef.current?.blur();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  function handleSelect(entityKey: string, item: SearchResultItem) {
    const config = ENTITY_CONFIG.find((c) => c.key === entityKey);
    if (!config) return;

    // Deals n'ont pas de page detail (pipeline), naviguer vers la pipeline
    const path = entityKey === 'deals' ? '/pipeline' : `${config.route}/${item.id}`;
    navigate(path);
    setQuery('');
    setIsOpen(false);
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      {/* Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (hasResults) setIsOpen(true); }}
          placeholder="Rechercher contacts, entreprises, deals..."
          className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
        />
      </div>

      {/* Dropdown resultats */}
      {isOpen && data && debouncedQuery.length >= MIN_QUERY_LENGTH && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-lg z-50 max-h-[400px] overflow-y-auto">
          {!hasResults && (
            <div className="px-4 py-3 text-sm text-slate-500">
              Aucun résultat pour « {debouncedQuery} »
            </div>
          )}

          {ENTITY_CONFIG.map(({ key, label, icon: Icon }) => {
            const items = data[key];
            if (!items || items.length === 0) return null;

            return (
              <div key={key}>
                <div className="px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider bg-slate-50 border-b border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                  </div>
                </div>
                {items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSelect(key, item)}
                    className={clsx(
                      'w-full text-left px-4 py-2.5 hover:bg-slate-50 transition-colors',
                      'flex items-center justify-between',
                    )}
                  >
                    <span className="text-sm font-medium text-slate-800">{item.label}</span>
                    {item.sub && (
                      <span className="text-xs text-slate-400 ml-2">{item.sub}</span>
                    )}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
