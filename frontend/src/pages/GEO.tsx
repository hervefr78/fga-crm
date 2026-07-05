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
import { Eye, ShieldAlert, Plus, Play } from 'lucide-react';

import { useAuth } from '../contexts/useAuth';
import { isAdmin, isManagerOrAbove } from '../types';
import {
  listGeoBrands, getGeoDashboard, getGeoGaps, getGeoAlerts,
  getGeoHealth, listGeoPrompts, triggerGeoRun, triggerGeoRemeasure,
  createGeoBrand, createGeoPrompt, deleteGeoPrompt, getGeoBrandsOverview,
} from '../api/geo';
import type { GeoEngine, GeoIntent } from '../types/geo';
import { Button, Modal } from '../components/ui';
import { BrandModal } from '../components/geo/BrandModal';
import { PromptsModal } from '../components/geo/PromptsModal';
import { GeoDashboard } from '../components/geo/GeoDashboard';
import { PageHeader } from '../components/geo/GeoAtoms';
import { ENGINES, extractError, slugify } from '../components/geo/geoUtils';

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

  return (
    <div className="px-8 py-7 space-y-6">
      <PageHeader />

      {/* ===== Tableau de bord GEO (rendu extrait dans GeoDashboard) ===== */}
      <GeoDashboard
        brands={brands}
        brandsOverview={brandsOverview}
        activeBrandId={activeBrandId}
        selectedEngine={selectedEngine}
        period={period}
        canWrite={canWrite}
        prompts={prompts}
        dashboard={dashboard}
        dashLoading={dashLoading}
        gaps={gaps}
        gapsLoading={gapsLoading}
        alerts={alerts}
        health={health}
        successMsg={successMsg}
        errorMsg={errorMsg}
        remeasurePending={remeasureMutation.isPending}
        onSelectBrand={setSelectedBrandId}
        setSelectedEngine={setSelectedEngine}
        setPeriod={setPeriod}
        onOpenPrompts={() => setPromptsModalOpen(true)}
        onOpenBrandModal={() => setBrandModalOpen(true)}
        onOpenRunModal={() => setRunModalOpen(true)}
        onRemeasure={() => remeasureMutation.mutate()}
        onDismissSuccess={() => setSuccessMsg(null)}
        onDismissError={() => setErrorMsg(null)}
      />

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

