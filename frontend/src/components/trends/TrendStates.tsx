// =============================================================================
// FGA CRM - Trends : en-tete, champs de filtre, etats (extraits de Trends.tsx)
// =============================================================================

import type { ReactNode } from 'react';
import { AlertTriangle, Loader2, Search } from 'lucide-react';

export function PageHeader() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-800">
        Trends — Signal de marche
      </h1>
      <p className="text-sm text-slate-500 mt-1">
        Lecture de la demande de recherche par categorie, pays et periode. Indice
        d&apos;interet relatif (0-100), pas un volume absolu.
      </p>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

export function SelectMini({
  value, onChange, options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export function RunningState({ mode }: { mode: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
      <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
      <p className="text-sm text-slate-600">
        Analyse {mode === 'deep' ? 'profonde' : 'rapide'} en cours…
      </p>
      <p className="text-xs text-slate-400">Le rapport s&apos;affichera automatiquement.</p>
    </div>
  );
}

export function FailedState({ error }: { error: string | null }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
      <div className="w-12 h-12 rounded-lg bg-red-50 flex items-center justify-center">
        <AlertTriangle className="w-6 h-6 text-red-500" />
      </div>
      <p className="text-sm text-slate-600">L&apos;analyse a echoue.</p>
      {error && <p className="text-xs text-slate-400 max-w-md">{error}</p>}
    </div>
  );
}

export function EmptyState({ categories }: { categories: number }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
      <div className="w-12 h-12 rounded-lg bg-slate-50 flex items-center justify-center">
        <Search className="w-6 h-6 text-slate-400" />
      </div>
      <p className="text-sm text-slate-500 max-w-sm">
        {categories === 0
          ? 'Aucune categorie disponible pour le moment.'
          : "Choisissez une categorie et lancez une analyse pour afficher les tendances."}
      </p>
    </div>
  );
}
