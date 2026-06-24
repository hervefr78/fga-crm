// =============================================================================
// FGA CRM - Page Integrations (Startup Radar sync)
// =============================================================================

import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, CheckCircle, AlertTriangle, Building2, Users, Briefcase, FileText } from 'lucide-react';
import { syncStartupRadar, getSyncStatus } from '../api/client';
import type { SyncStatus } from '../types';

// Intervalle de polling du statut pendant une sync en cours (ms)
const SYNC_POLL_INTERVAL = 3000;

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const prevStatusRef = useRef<string | undefined>(undefined);

  // Statut de la full sync. Tant qu'une sync tourne (status='running'), on poll
  // toutes les 3s ; sinon on arrete (refetchInterval=false).
  const { data: status } = useQuery<SyncStatus>({
    queryKey: ['sync-status'],
    queryFn: getSyncStatus,
    refetchInterval: (query) =>
      query.state.data?.status === 'running' ? SYNC_POLL_INTERVAL : false,
  });

  const isRunning = status?.status === 'running';
  const isFailed = status?.status === 'failed';

  // Mutation : lance la sync (202). Le polling du statut prend le relais.
  const syncMutation = useMutation({
    mutationFn: syncStartupRadar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sync-status'] });
    },
  });

  // Transition running -> completed : rafraichir les listes impactees.
  useEffect(() => {
    if (prevStatusRef.current === 'running' && status?.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['activities'] });
    }
    prevStatusRef.current = status?.status;
  }, [status?.status, queryClient]);

  // Source unique de verite : le dernier resultat vient du statut (Redis).
  const displayResult = status?.last_result ?? null;
  const hasErrors = displayResult && displayResult.errors.length > 0;
  const busy = isRunning || syncMutation.isPending;
  const totalCreated = displayResult
    ? displayResult.companies_created + displayResult.contacts_created +
      displayResult.investors_created + displayResult.audits_created
    : 0;
  const totalUpdated = displayResult
    ? displayResult.companies_updated + displayResult.contacts_updated +
      displayResult.investors_updated
    : 0;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Integrations</h1>

      {/* Carte Startup Radar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-50 rounded-lg flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-800">Startup Radar</h2>
              <p className="text-sm text-slate-500">
                Synchroniser les startups, contacts, investisseurs et audits
              </p>
            </div>
          </div>

          <button
            onClick={() => syncMutation.mutate()}
            disabled={busy}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} />
            {busy ? 'Synchronisation...' : 'Synchroniser'}
          </button>
        </div>

        {/* Contenu */}
        <div className="px-6 py-5">
          {/* Etat initial — jamais synchro */}
          {!displayResult && !busy && !isFailed && (
            <div className="text-center py-8 text-slate-400">
              <RefreshCw className="w-12 h-12 mx-auto mb-3 text-slate-300" />
              <p className="text-sm">Aucune synchronisation effectuee</p>
              <p className="text-xs mt-1">Cliquez sur "Synchroniser" pour importer les donnees de Startup Radar</p>
            </div>
          )}

          {/* En cours (tache de fond — statut poll toutes les 3s) */}
          {busy && (
            <div className="text-center py-8">
              <RefreshCw className="w-12 h-12 mx-auto mb-3 text-indigo-400 animate-spin" />
              <p className="text-sm text-slate-600 font-medium">Synchronisation en cours...</p>
              <p className="text-xs text-slate-400 mt-1">
                Elle tourne en arriere-plan — vous pouvez quitter cette page, elle continuera.
              </p>
            </div>
          )}

          {/* Erreur de lancement (mutation : 409 deja en cours, 503 file indispo) */}
          {syncMutation.isError && !busy && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <div className="flex items-center gap-2 text-red-700">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm font-medium">Lancement impossible</span>
              </div>
              <p className="text-sm text-red-600 mt-1">
                {(syncMutation.error as { response?: { data?: { detail?: string } } })
                  ?.response?.data?.detail ||
                  (syncMutation.error as Error)?.message ||
                  'Une erreur est survenue'}
              </p>
            </div>
          )}

          {/* Sync echouee (statut Redis : la task a leve une exception) */}
          {isFailed && !busy && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <div className="flex items-center gap-2 text-red-700">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm font-medium">La derniere synchronisation a echoue</span>
              </div>
              <p className="text-sm text-red-600 mt-1">
                {status?.error || 'Erreur inconnue'}
              </p>
            </div>
          )}

          {/* Resultat */}
          {displayResult && !isRunning && (
            <>
              {/* Resume */}
              <div className="flex items-center gap-2 mb-4">
                {hasErrors ? (
                  <AlertTriangle className="w-5 h-5 text-amber-500" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                )}
                <span className="text-sm font-medium text-slate-700">
                  {totalCreated} element{totalCreated > 1 ? 's' : ''} cree{totalCreated > 1 ? 's' : ''}
                  {totalUpdated > 0 && `, ${totalUpdated} mis a jour`}
                  {hasErrors && ` — ${displayResult.errors.length} erreur${displayResult.errors.length > 1 ? 's' : ''}`}
                </span>
              </div>

              {/* Grille de stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <StatCard
                  icon={Building2}
                  label="Entreprises"
                  created={displayResult.companies_created}
                  updated={displayResult.companies_updated}
                  color="blue"
                />
                <StatCard
                  icon={Users}
                  label="Contacts"
                  created={displayResult.contacts_created}
                  updated={displayResult.contacts_updated}
                  color="emerald"
                />
                <StatCard
                  icon={Briefcase}
                  label="Investisseurs"
                  created={displayResult.investors_created}
                  updated={displayResult.investors_updated}
                  color="purple"
                />
                <StatCard
                  icon={FileText}
                  label="Audits"
                  created={displayResult.audits_created}
                  updated={0}
                  color="amber"
                />
              </div>

              {/* Erreurs */}
              {hasErrors && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-amber-700 mb-2">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-medium">
                      {displayResult.errors.length} erreur{displayResult.errors.length > 1 ? 's' : ''}
                    </span>
                  </div>
                  <ul className="space-y-1">
                    {displayResult.errors.map((err, i) => (
                      <li key={i} className="text-xs text-amber-600">• {err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}


// ---------- Composant StatCard ----------

const COLOR_MAP: Record<string, { bg: string; icon: string; text: string }> = {
  blue: { bg: 'bg-blue-50', icon: 'text-blue-500', text: 'text-blue-700' },
  emerald: { bg: 'bg-emerald-50', icon: 'text-emerald-500', text: 'text-emerald-700' },
  purple: { bg: 'bg-purple-50', icon: 'text-purple-500', text: 'text-purple-700' },
  amber: { bg: 'bg-amber-50', icon: 'text-amber-500', text: 'text-amber-700' },
};

function StatCard({
  icon: Icon,
  label,
  created,
  updated,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  created: number;
  updated: number;
  color: string;
}) {
  const c = COLOR_MAP[color] ?? COLOR_MAP.blue;

  return (
    <div className={`${c.bg} rounded-lg p-3`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 ${c.icon}`} />
        <span className={`text-xs font-medium ${c.text}`}>{label}</span>
      </div>
      <div className="text-lg font-bold text-slate-800">+{created}</div>
      {updated > 0 && (
        <div className="text-xs text-slate-500">~{updated} mis a jour</div>
      )}
    </div>
  );
}
