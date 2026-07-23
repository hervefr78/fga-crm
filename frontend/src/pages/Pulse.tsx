// =============================================================================
// FGA CRM - Radar & Calendrier (FGA Pulse) — onglet Sprint 0 (etat vide)
// =============================================================================
// Pulse est un service autonome : radar de themes LinkedIn + calendrier editorial.
// Sprint 0 : l'onglet affiche l'etat du service (/health) et un etat vide ; les
// vues Radar / Opportunites / Calendrier arrivent aux sprints suivants.
// RBAC : manager+ (comme les autres outils Marketing).
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { Radar, ShieldAlert, Compass } from 'lucide-react';

import { useAuth } from '../contexts/useAuth';
import { isManagerOrAbove } from '../types';
import { getPulseHealth } from '../api/pulse';
import { Badge, EmptyState } from '../components/ui';

// Badge d'etat du service Pulse (sonde /health, rafraichie toutes les 30 s).
function HealthBadge() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['pulse-health'],
    queryFn: getPulseHealth,
    retry: false,
    refetchInterval: 30_000,
  });

  if (isLoading) return <Badge variant="default">Vérification…</Badge>;
  if (isError || !data) return <Badge variant="danger">Service injoignable</Badge>;
  if (data.status === 'ok') return <Badge variant="success">Service en ligne</Badge>;
  return <Badge variant="warning">{`Dégradé (db ${data.db} · redis ${data.redis})`}</Badge>;
}

export default function PulsePage() {
  const { user } = useAuth();

  // RBAC in-page (meme pattern que GEO/Trends) : les sales n'ont pas acces.
  if (!isManagerOrAbove(user)) {
    return (
      <div className="p-8 text-center text-slate-400">
        <ShieldAlert className="w-6 h-6 mx-auto mb-2" />
        <p className="text-sm">Accès non autorisé</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Radar className="w-6 h-6 text-primary-500" />
          <div>
            <h1 className="text-xl font-semibold text-slate-800">Radar &amp; Calendrier</h1>
            <p className="text-sm text-slate-500">
              Radar de thèmes LinkedIn + calendrier éditorial (FGA Pulse)
            </p>
          </div>
        </div>
        <HealthBadge />
      </div>

      <div className="bg-white border border-slate-200 rounded-lg">
        <EmptyState
          icon={Compass}
          message="Le radar de thèmes, les opportunités et le calendrier arrivent aux prochains sprints. Cet onglet est connecté au service FGA Pulse."
        />
      </div>
    </div>
  );
}
