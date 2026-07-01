// =============================================================================
// FGA CRM - GEO Dashboard (Generative Engine Optimization)
// =============================================================================
// Mesure la visibilite des marques dans les moteurs IA (ChatGPT, Perplexite...)
// et detecte les gaps pour alimenter la boucle d'optimisation P4.
//
// RBAC : admin + manager uniquement (les sales recoivent un ecran "non autorise").
// Les actions d'ecriture (trigger run, remeasure) sont reservees aux admins.
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity, TrendingUp, Eye, Star, AlertTriangle, CheckCircle, XCircle,
  Play, RefreshCw, ShieldAlert, Plus, MessageSquarePlus,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import clsx from 'clsx';

import { useAuth } from '../contexts/useAuth';
import { isAdmin, isManagerOrAbove } from '../types';
import {
  listGeoBrands, getGeoDashboard, getGeoGaps, getGeoAlerts,
  getGeoHealth, listGeoPrompts, triggerGeoRun, triggerGeoRemeasure,
  createGeoBrand, createGeoPrompt, deleteGeoPrompt, getGeoBrandsOverview,
} from '../api/geo';
import type { GeoEngine, GeoIntent } from '../types/geo';
import { Button, Modal } from '../components/ui';
import { BrandSelector } from '../components/geo/BrandSelector';
import { BrandModal } from '../components/geo/BrandModal';
import { PromptsModal } from '../components/geo/PromptsModal';
import { GapRow, KpiTile, PageHeader, RankList } from '../components/geo/GeoAtoms';
import {
  COLOR_SOV, COLOR_VISIBILITY, ENGINES, PERIODS,
  avgMetric, extractError, formatRate, sentimentLabel, slugify,
} from '../components/geo/geoUtils';

// slug derive du nom : minuscules, alphanumerique + tirets.
// =============================================================================
// Page
// =============================================================================

export default function GEOPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // ---- Etats locaux ----
  const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);
  const [selectedEngine, setSelectedEngine] = useState<GeoEngine>('perplexity');
  const [period, setPeriod] = useState<'7' | '30' | '90'>('30');
  const [runModalOpen, setRunModalOpen] = useState(false);
  // Message de succes des mutations Celery (task_id + nb runs planifies)
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Gestion marques / prompts (admin)
  const [brandModalOpen, setBrandModalOpen] = useState(false);
  const [brandName, setBrandName] = useState('');
  const [brandAliases, setBrandAliases] = useState('');
  const [promptsModalOpen, setPromptsModalOpen] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [promptIntent, setPromptIntent] = useState<GeoIntent>('informationnel');

  const canWrite = isAdmin(user);
  // RBAC : les sales n'ont pas acces. Le flag est evalue APRES tous les hooks
  // (rules-of-hooks) — on coupe simplement les requetes pour eux via `enabled`.
  const hasAccess = isManagerOrAbove(user);

  // ---- Queries ----
  const { data: brands = [], isLoading: brandsLoading } = useQuery({
    queryKey: ['geo-brands'],
    queryFn: () => listGeoBrands(true), // marques possedees uniquement
    enabled: hasAccess,
  });

  // Marque active : selection explicite, sinon la premiere disponible
  const activeBrandId = selectedBrandId ?? brands[0]?.id ?? null;

  // Apercu de toutes les marques + leur visibilite (selecteur avec mini-score).
  // Depend du moteur/periode pour que le mini-score colle au dashboard affiche.
  const { data: brandsOverview = [] } = useQuery({
    queryKey: ['geo-brands-overview', selectedEngine, period],
    queryFn: () => getGeoBrandsOverview(selectedEngine, parseInt(period, 10)),
    enabled: hasAccess,
  });

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['geo-dashboard', activeBrandId, selectedEngine, period],
    queryFn: () => {
      const dateTo = new Date().toISOString().slice(0, 10);
      const dateFrom = new Date(Date.now() - parseInt(period, 10) * 86400000).toISOString().slice(0, 10);
      return getGeoDashboard(activeBrandId!, selectedEngine, dateFrom, dateTo);
    },
    enabled: hasAccess && !!activeBrandId,
  });

  const { data: gaps = [], isLoading: gapsLoading } = useQuery({
    queryKey: ['geo-gaps', activeBrandId, selectedEngine, period],
    queryFn: () => getGeoGaps(activeBrandId!, selectedEngine, parseInt(period, 10)),
    enabled: hasAccess && !!activeBrandId,
    retry: false,
  });

  const { data: alerts = [] } = useQuery({
    queryKey: ['geo-alerts', activeBrandId, selectedEngine],
    queryFn: () => getGeoAlerts(activeBrandId!, selectedEngine),
    enabled: hasAccess && !!activeBrandId,
    retry: false,
  });

  // Health : admin only (le backend renvoie 403 aux managers)
  const { data: health = [] } = useQuery({
    queryKey: ['geo-health'],
    queryFn: getGeoHealth,
    enabled: isAdmin(user),
    retry: false,
  });

  const { data: prompts = [] } = useQuery({
    queryKey: ['geo-prompts', activeBrandId],
    queryFn: () => listGeoPrompts(activeBrandId!),
    enabled: hasAccess && !!activeBrandId,
  });

  // ---- Mutations ----
  const runMutation = useMutation({
    mutationFn: () =>
      triggerGeoRun({
        brand_id: activeBrandId!,
        engine: selectedEngine,
        prompt_ids: prompts.map((p) => p.id),
      }),
    onSuccess: (data) => {
      setRunModalOpen(false);
      setErrorMsg(null);
      setSuccessMsg(
        `Run planifie : ${data.runs_scheduled} mesure(s) (task ${data.task_id}).`,
      );
    },
    onError: (err: unknown) => {
      setErrorMsg(extractError(err, 'Echec du declenchement du run.'));
    },
  });

  const remeasureMutation = useMutation({
    mutationFn: () =>
      triggerGeoRemeasure(activeBrandId!, selectedEngine, parseInt(period, 10)),
    onSuccess: (data) => {
      setErrorMsg(null);
      setSuccessMsg(
        `Re-mesure planifiee : ${data.runs_scheduled} mesure(s) (task ${data.task_id}).`,
      );
      // Rafraichir les gaps apres declenchement
      void queryClient
        .invalidateQueries({ queryKey: ['geo-gaps', activeBrandId] })
        .catch((e) => console.error('[GEO] invalidate gaps', e));
    },
    onError: (err: unknown) => {
      setErrorMsg(extractError(err, 'Echec de la re-mesure.'));
    },
  });

  // ---- Mutations gestion marques / prompts (admin) ----
  const createBrandMutation = useMutation({
    mutationFn: () =>
      createGeoBrand({
        name: brandName.trim(),
        slug: slugify(brandName),
        aliases: brandAliases.split(',').map((a) => a.trim()).filter(Boolean),
        is_owned: true,
      }),
    onSuccess: (brand) => {
      setBrandModalOpen(false);
      setBrandName('');
      setBrandAliases('');
      setErrorMsg(null);
      setSuccessMsg(`Marque « ${brand.name} » creee.`);
      setSelectedBrandId(brand.id);
      void queryClient.invalidateQueries({ queryKey: ['geo-brands'] });
    },
    onError: (err: unknown) => setErrorMsg(extractError(err, 'Echec de la creation de la marque.')),
  });

  const createPromptMutation = useMutation({
    mutationFn: () =>
      createGeoPrompt(activeBrandId!, { text: promptText.trim(), intent: promptIntent }),
    onSuccess: () => {
      setPromptText('');
      setErrorMsg(null);
      void queryClient.invalidateQueries({ queryKey: ['geo-prompts', activeBrandId] });
    },
    onError: (err: unknown) => setErrorMsg(extractError(err, 'Echec de la creation du prompt.')),
  });

  const deletePromptMutation = useMutation({
    mutationFn: (promptId: string) => deleteGeoPrompt(activeBrandId!, promptId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['geo-prompts', activeBrandId] });
    },
    onError: (err: unknown) => setErrorMsg(extractError(err, 'Echec de la suppression du prompt.')),
  });

  // ---- Garde RBAC (apres tous les hooks — rules-of-hooks) ----
  if (!hasAccess) {
    return (
      <div className="px-8 py-7">
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-red-50 flex items-center justify-center">
            <ShieldAlert className="w-6 h-6 text-red-500" />
          </div>
          <h1 className="text-lg font-semibold text-slate-800">Acces non autorise</h1>
          <p className="text-sm text-slate-500 max-w-sm">
            Le module GEO est reserve aux administrateurs et managers.
          </p>
        </div>
      </div>
    );
  }

  // ---- Etats globaux de chargement / vide ----
  if (brandsLoading) {
    return <div className="px-8 py-7 text-sm text-slate-500">Chargement...</div>;
  }

  if (!activeBrandId) {
    return (
      <div className="px-8 py-7">
        <PageHeader />
        <div className="mt-6 bg-white border border-slate-200 rounded-xl shadow-sm p-12 flex flex-col items-center text-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-slate-50 flex items-center justify-center">
            <Eye className="w-6 h-6 text-slate-400" />
          </div>
          <p className="text-sm text-slate-500">
            Aucune marque configuree. Ajoutez une marque possedee pour commencer le suivi GEO.
          </p>
          {canWrite && (
            <Button variant="primary" size="sm" icon={Plus} onClick={() => setBrandModalOpen(true)}>
              Ajouter une marque
            </Button>
          )}
        </div>
        <BrandModal
          open={brandModalOpen}
          onClose={() => setBrandModalOpen(false)}
          canWrite={canWrite}
          name={brandName}
          setName={setBrandName}
          aliases={brandAliases}
          setAliases={setBrandAliases}
          submitting={createBrandMutation.isPending}
          onSubmit={() => createBrandMutation.mutate()}
        />
      </div>
    );
  }

  const metrics = dashboard?.metrics ?? [];
  const hasActiveAlerts = alerts.some(
    (a) => a.severity === 'critical' || a.severity === 'warning',
  );

  // Donnees du LineChart, triees par jour
  const chartData = [...metrics]
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((m) => ({
      date: m.day,
      sov: m.sov ?? 0,
      visibility: m.visibility_rate ?? 0,
    }));

  // KPI agreges
  const kVisibility = avgMetric(metrics, 'visibility_rate');
  const kSov = avgMetric(metrics, 'sov');
  const kSovWeighted = avgMetric(metrics, 'sov_weighted');
  const kSentiment = avgMetric(metrics, 'sentiment_avg');

  return (
    <div className="px-8 py-7 space-y-6">
      <PageHeader />

      {/* ===== FilterBar : Brand tabs | Engine | Periode ===== */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Selecteur de marque : dropdown recherchable + mini-score */}
        <BrandSelector
          brands={brandsOverview}
          fallbackName={brands.find((b) => b.id === activeBrandId)?.name ?? null}
          activeBrandId={activeBrandId}
          onSelect={(id) => setSelectedBrandId(id)}
          canWrite={canWrite}
          onAddBrand={() => setBrandModalOpen(true)}
        />

        <div className="h-5 w-px bg-slate-200" aria-hidden />

        {/* Engine selector */}
        <div className="flex items-center gap-1 flex-wrap">
          {ENGINES.map((e) => {
            const h = health.find((x) => x.engine === e.value);
            const unconfigured = h?.status === 'unconfigured';
            return (
              <button
                key={e.value}
                type="button"
                onClick={() => setSelectedEngine(e.value)}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors inline-flex items-center gap-1.5',
                  e.value === selectedEngine
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700',
                )}
              >
                {e.label}
                {unconfigured && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-slate-200 text-slate-500">
                    Non configure
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="h-5 w-px bg-slate-200" aria-hidden />

        {/* Periode */}
        <label className="sr-only" htmlFor="geo-period">Periode</label>
        <select
          id="geo-period"
          value={period}
          onChange={(e) => setPeriod(e.target.value as '7' | '30' | '90')}
          className="px-3 py-1.5 rounded-lg text-sm border border-slate-200 text-slate-700 bg-white"
        >
          {PERIODS.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>

        {/* Actions (admin only) */}
        {canWrite && (
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={MessageSquarePlus}
              onClick={() => setPromptsModalOpen(true)}
            >
              Prompts ({prompts.length})
            </Button>
            <Button variant="secondary" size="sm" icon={Plus} onClick={() => setBrandModalOpen(true)}>
              Marque
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={Play}
              disabled={prompts.length === 0}
              title={prompts.length === 0 ? 'Aucun prompt a mesurer' : undefined}
              onClick={() => setRunModalOpen(true)}
            >
              Lancer un run
            </Button>
          </div>
        )}
      </div>

      {/* ===== Bandeaux de feedback mutation ===== */}
      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-emerald-800 flex-1">{successMsg}</p>
          <button
            type="button"
            onClick={() => setSuccessMsg(null)}
            className="text-emerald-500 hover:text-emerald-700"
            aria-label="Fermer"
          >
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-800 flex-1">{errorMsg}</p>
          <button
            type="button"
            onClick={() => setErrorMsg(null)}
            className="text-red-500 hover:text-red-700"
            aria-label="Fermer"
          >
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ===== Alert banner (P3) ===== */}
      {hasActiveAlerts && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">
              {alerts.length} alerte(s) detectee(s)
            </p>
            {alerts.slice(0, 3).map((a, i) => (
              <p key={i} className="text-xs text-amber-700 mt-1">• {a.message}</p>
            ))}
          </div>
        </div>
      )}

      {/* ===== Contenu principal : depend du chargement dashboard ===== */}
      {dashLoading ? (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 text-center text-sm text-slate-500">
          Chargement du tableau de bord...
        </div>
      ) : (
        <>
          {/* ===== KPI Strip (4 colonnes) ===== */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiTile label="Visibilite" value={formatRate(kVisibility)} icon={Eye} color="text-blue-600" bg="bg-blue-50" />
            <KpiTile label="Share of Voice" value={formatRate(kSov)} icon={Activity} color="text-indigo-600" bg="bg-indigo-50" />
            <KpiTile label="SoV pondere" value={formatRate(kSovWeighted)} icon={TrendingUp} color="text-violet-600" bg="bg-violet-50" />
            <KpiTile label="Sentiment" value={sentimentLabel(kSentiment)} icon={Star} color="text-amber-600" bg="bg-amber-50" />
          </div>

          {/* ===== Gaps a traiter (P4) — juste sous les KPI ===== */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <AlertTriangle className="w-3.5 h-3.5 text-slate-400" />
                Gaps a traiter
                <span className="text-xs text-slate-400 tabular-nums font-normal">· {gaps.length}</span>
              </div>
              {canWrite && gaps.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  loading={remeasureMutation.isPending}
                  onClick={() => remeasureMutation.mutate()}
                >
                  Declencher re-mesure
                </Button>
              )}
            </div>

            {gapsLoading ? (
              <div className="py-8 text-center text-sm text-slate-400">Chargement des gaps...</div>
            ) : gaps.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-400">
                Aucun gap detecte sur la periode — la marque est bien positionnee.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                      <th className="px-4 py-2 font-medium">Prompt</th>
                      <th className="px-4 py-2 font-medium">Intention</th>
                      <th className="px-4 py-2 font-medium">Priorite</th>
                      <th className="px-4 py-2 font-medium">Visibilite</th>
                      <th className="px-4 py-2 font-medium">Suggestion d'action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {gaps.map((g) => (
                      <GapRow key={g.prompt_id} gap={g} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ===== Grid 2/3 main (chart) + 1/3 side (sources/concurrents) ===== */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main : LineChart SoV / Visibilite (self-start : ne s'etire pas
                a la hauteur de la colonne laterale, evite le grand vide) */}
            <div className="lg:col-span-2 self-start bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 text-sm font-semibold text-slate-800">
                <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
                Evolution SoV / Visibilite
              </div>
              <div className="px-4 py-4">
                {chartData.length === 0 ? (
                  <div className="h-[200px] flex items-center justify-center text-sm text-slate-400">
                    Aucune metrique sur la periode
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line type="monotone" dataKey="sov" name="SoV" stroke={COLOR_SOV} strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="visibility" name="Visibilite" stroke={COLOR_VISIBILITY} strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* Side : Top sources + Top concurrents */}
            <div className="space-y-6">
              <RankList
                title="Top sources"
                icon={Activity}
                items={(dashboard?.top_sources ?? []).map((s) => ({ label: s.domain, count: s.count }))}
                emptyLabel="Aucune source citee"
              />
              <RankList
                title="Top concurrents"
                icon={Star}
                items={(dashboard?.top_competitors ?? []).map((c) => ({ label: c.nom, count: c.mentions }))}
                emptyLabel="Aucun concurrent detecte"
              />
            </div>
          </div>
        </>
      )}

      {/* ===== Health moteurs (admin only) ===== */}
      {isAdmin(user) && health.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 text-sm font-semibold text-slate-800">
            <CheckCircle className="w-3.5 h-3.5 text-slate-400" />
            Health moteurs
          </div>
          <div className="p-4 flex flex-wrap gap-2">
            {health.map((h) => (
              <div
                key={h.engine}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200"
                title={h.error ?? undefined}
              >
                {h.status === 'ok' ? (
                  <CheckCircle className="w-4 h-4 text-emerald-500" />
                ) : h.status === 'error' ? (
                  <XCircle className="w-4 h-4 text-red-500" />
                ) : (
                  <div className="w-4 h-4 rounded-full bg-slate-300" />
                )}
                <span className="text-xs text-slate-700">{h.engine}</span>
                <span
                  className={clsx(
                    'text-xs',
                    h.status === 'ok'
                      ? 'text-emerald-600'
                      : h.status === 'error'
                        ? 'text-red-500'
                        : 'text-slate-400',
                  )}
                >
                  {h.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===== Modale de confirmation : lancer un run (admin only) ===== */}
      {canWrite && (
        <Modal
          open={runModalOpen}
          onClose={() => setRunModalOpen(false)}
          title="Lancer un run GEO"
          footer={
            <>
              <Button variant="secondary" onClick={() => setRunModalOpen(false)}>
                Annuler
              </Button>
              <Button
                variant="primary"
                icon={Play}
                loading={runMutation.isPending}
                onClick={() => runMutation.mutate()}
              >
                Confirmer
              </Button>
            </>
          }
        >
          <p className="text-sm text-slate-600">
            Declencher une mesure sur le moteur{' '}
            <span className="font-medium text-slate-800">
              {ENGINES.find((e) => e.value === selectedEngine)?.label ?? selectedEngine}
            </span>{' '}
            pour les <span className="font-medium text-slate-800">{prompts.length}</span> prompt(s)
            actif(s) de cette marque.
          </p>
          <p className="text-xs text-slate-400 mt-2">
            Le traitement est asynchrone (Celery). Les resultats apparaitront une fois les mesures collectees.
          </p>
        </Modal>
      )}

      <BrandModal
        open={brandModalOpen}
        onClose={() => setBrandModalOpen(false)}
        canWrite={canWrite}
        name={brandName}
        setName={setBrandName}
        aliases={brandAliases}
        setAliases={setBrandAliases}
        submitting={createBrandMutation.isPending}
        onSubmit={() => createBrandMutation.mutate()}
      />
      <PromptsModal
        open={promptsModalOpen}
        onClose={() => setPromptsModalOpen(false)}
        canWrite={canWrite}
        prompts={prompts}
        text={promptText}
        setText={setPromptText}
        intent={promptIntent}
        setIntent={setPromptIntent}
        creating={createPromptMutation.isPending}
        onCreate={() => createPromptMutation.mutate()}
        onDelete={(id) => deletePromptMutation.mutate(id)}
      />
    </div>
  );
}

// -----------------------------------------------------------------------------
// Sous-composants
// -----------------------------------------------------------------------------

