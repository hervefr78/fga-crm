// =============================================================================
// FGA CRM - Enrichissement : table des jobs (statut + stats)
// =============================================================================

import clsx from 'clsx';

import type { EnrichmentJob, EnrichmentJobStatus } from '../../types/enrichment';

const STATUS_STYLE: Record<EnrichmentJobStatus, string> = {
  queued: 'bg-slate-100 text-slate-600',
  running: 'bg-blue-50 text-blue-700',
  awaiting_results: 'bg-amber-50 text-amber-700',
  done: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-600',
};

const STATUS_LABEL: Record<EnrichmentJobStatus, string> = {
  queued: 'En file',
  running: 'En cours',
  awaiting_results: 'En attente (webhook)',
  done: 'Termine',
  failed: 'Echec',
};

const MODE_LABEL: Record<string, string> = {
  company: 'A la demande',
  batch: 'Batch',
  icp: 'Batch / ICP',
};

function fmtDate(iso: string): string {
  return iso ? iso.slice(0, 16).replace('T', ' ') : '—';
}

export function EnrichmentJobsTable({ jobs }: { jobs: EnrichmentJob[] }) {
  if (jobs.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm py-10 text-center text-sm text-slate-400">
        Aucun enrichissement lance pour le moment.
      </div>
    );
  }
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
              <th className="px-4 py-2 font-medium">Mode</th>
              <th className="px-4 py-2 font-medium">Statut</th>
              <th className="px-4 py-2 font-medium">Societes</th>
              <th className="px-4 py-2 font-medium">Decideurs</th>
              <th className="px-4 py-2 font-medium">Emails valides</th>
              <th className="px-4 py-2 font-medium">Credits</th>
              <th className="px-4 py-2 font-medium">Lance le</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {jobs.map((j) => {
              const s = j.stats_json || {};
              return (
                <tr key={j.id} className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 text-slate-700">{MODE_LABEL[j.mode] ?? j.mode}</td>
                  <td className="px-4 py-2.5">
                    <span className={clsx(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      STATUS_STYLE[j.status],
                    )}>
                      {STATUS_LABEL[j.status]}
                    </span>
                    {j.status === 'failed' && j.error && (
                      <span className="ml-2 text-xs text-slate-400" title={j.error}>· detail</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-slate-700 tabular-nums">{s.companies ?? '—'}</td>
                  <td className="px-4 py-2.5 text-slate-700 tabular-nums">{s.people_found ?? '—'}</td>
                  <td className="px-4 py-2.5 text-slate-800 tabular-nums font-medium">{s.valid ?? '—'}</td>
                  <td className="px-4 py-2.5 text-slate-500 tabular-nums">{s.credits_spent ?? '—'}</td>
                  <td className="px-4 py-2.5 text-slate-500 tabular-nums">{fmtDate(j.created_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
