// =============================================================================
// FGA CRM - Drafts à valider (revue des drafts MCP : approuver / rejeter)
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileCheck, Check, X, AlertTriangle, Download } from 'lucide-react';

import { listPendingDrafts, updateDraftStatus, exportHeyReachCsv } from '../api/drafts';
import type { DraftReview, DraftBrand, DraftStatus } from '../types';
import { LoadingSpinner, EmptyState, Badge, Button, Tabs } from '../components/ui';

// ---------- Badge maps ----------

const BRAND_VARIANTS: Record<DraftBrand, 'default' | 'info' | 'success' | 'warning'> = {
  fga: 'info',
  nomo: 'success',
  ppd: 'warning',
};

const BRAND_LABELS: Record<DraftBrand, string> = {
  fga: 'FGA',
  nomo: 'nomo',
  ppd: 'PPD',
};

// Libelles FR des types de drafts. Fallback sur la valeur brute si type inconnu.
const TYPE_LABELS: Record<string, string> = {
  linkedin_invitation: 'Invitation LinkedIn',
  linkedin_dm: 'Message LinkedIn',
  linkedin_relance: 'Relance LinkedIn',
  linkedin_comment: 'Commentaire LinkedIn',
  linkedin_post: 'Post LinkedIn',
  linkedin_sequence_drafted: 'Séquence LinkedIn',
  email: 'Email',
  reddit_post: 'Post Reddit',
  reddit_comment: 'Commentaire Reddit',
};

// Onglets de filtre par marque. 'all' = aucun filtre brand cote API.
const BRAND_TABS: { key: string; label: string }[] = [
  { key: 'all', label: 'Toutes' },
  { key: 'fga', label: 'FGA' },
  { key: 'nomo', label: 'nomo' },
  { key: 'ppd', label: 'PPD' },
];

const MAX_AGE_HOURS = 48;
const PREVIEW_MAX = 280;

// Notice transitoire affichee sous le bouton d'export (skipped ou erreur).
type ExportNotice = { kind: 'info' | 'error'; message: string } | null;

export default function DraftsPage() {
  const queryClient = useQueryClient();
  const [brandFilter, setBrandFilter] = useState<string>('all');
  const [exporting, setExporting] = useState(false);
  const [exportNotice, setExportNotice] = useState<ExportNotice>(null);

  const brandParam: DraftBrand | undefined =
    brandFilter === 'all' ? undefined : (brandFilter as DraftBrand);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['drafts-review', 'pending', brandFilter],
    queryFn: () =>
      listPendingDrafts({ brand: brandParam, maxAgeHours: MAX_AGE_HOURS }),
  });

  // Mutation de changement de statut. On suit le draft_id en cours pour
  // desactiver UNIQUEMENT les boutons de la carte concernee pendant la requete.
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: DraftStatus }) =>
      updateDraftStatus(id, status),
    onSuccess: () => {
      // Refetch : le draft quitte la liste 'pending' une fois approuve/rejete.
      void queryClient.invalidateQueries({ queryKey: ['drafts-review', 'pending'] });
    },
  });

  const pendingId =
    statusMutation.isPending && statusMutation.variables
      ? statusMutation.variables.id
      : null;

  const handleApprove = (id: string) => {
    statusMutation.mutate({ id, status: 'approved' });
  };

  const handleReject = (id: string) => {
    statusMutation.mutate({ id, status: 'rejected' });
  };

  // Export CSV HeyReach des drafts approuves pour la marque filtree (ou toutes).
  // On declenche le telechargement cote navigateur a partir du blob backend.
  const handleExportCsv = async () => {
    setExporting(true);
    setExportNotice(null);
    try {
      const { blob, filename, skipped } = await exportHeyReachCsv(brandParam);

      // Telechargement navigateur via object URL (revoque apres clic).
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      if (skipped > 0) {
        setExportNotice({
          kind: 'info',
          message: `${skipped} lead${skipped > 1 ? 's' : ''} ignoré${skipped > 1 ? 's' : ''} — pas d'URL LinkedIn ou d'invitation approuvée.`,
        });
      }
    } catch (err) {
      console.error('[Drafts] Export CSV HeyReach échoué :', err);
      setExportNotice({
        kind: 'error',
        message: "Échec de l'export CSV. Vérifiez votre connexion et réessayez.",
      });
    } finally {
      setExporting(false);
    }
  };

  const drafts = data ?? [];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Drafts à valider</h1>
          <p className="text-slate-400 text-sm mt-1">
            {isLoading ? 'Chargement…' : `${drafts.length} draft${drafts.length > 1 ? 's' : ''} en attente`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            icon={Download}
            onClick={handleExportCsv}
            loading={exporting}
            disabled={exporting}
            size="sm"
          >
            Exporter CSV HeyReach
          </Button>
        </div>
      </div>

      {/* Filtre par marque */}
      <div className="mb-5">
        <Tabs tabs={BRAND_TABS} activeTab={brandFilter} onChange={setBrandFilter} />
      </div>

      {/* Notice d'export (skipped ou erreur) — jamais d'ecran blanc (DC7) */}
      {exportNotice && (
        <div
          role="status"
          aria-live="polite"
          className={
            exportNotice.kind === 'error'
              ? 'mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700'
              : 'mb-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-700'
          }
        >
          {exportNotice.message}
        </div>
      )}

      {/* Contenu : loading / error / empty / success (DC5, DC7) */}
      {isLoading ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <LoadingSpinner message="Chargement des drafts…" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center">
          <AlertTriangle className="w-6 h-6 mx-auto mb-2 text-amber-500" />
          <p className="text-sm text-slate-600 mb-4">
            Impossible de charger les drafts. Vérifiez votre connexion et réessayez.
          </p>
          <Button variant="secondary" size="sm" onClick={() => void refetch()} loading={isFetching}>
            Réessayer
          </Button>
        </div>
      ) : drafts.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <EmptyState icon={FileCheck} message="Aucun draft en attente de validation" />
        </div>
      ) : (
        <div className="space-y-4">
          {drafts.map((draft: DraftReview) => {
            const isRowPending = pendingId === draft.draft_id;
            const charCount = draft.content.length;
            const preview =
              draft.content.length > PREVIEW_MAX
                ? draft.content.slice(0, PREVIEW_MAX) + '…'
                : draft.content;

            return (
              <div
                key={draft.draft_id}
                className="bg-white rounded-xl border border-slate-200 shadow-sm p-5"
              >
                {/* Ligne meta : marque, type, voice-check */}
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <Badge variant={BRAND_VARIANTS[draft.brand] ?? 'default'}>
                    {BRAND_LABELS[draft.brand] ?? draft.brand}
                  </Badge>
                  <span className="text-sm font-medium text-slate-700">
                    {TYPE_LABELS[draft.type] ?? draft.type}
                  </span>
                  {draft.voice_check_passed ? (
                    <Badge variant="success">voix ✓</Badge>
                  ) : (
                    <Badge variant="warning">voix ✗</Badge>
                  )}
                  {draft.sequence_day !== null && (
                    <span className="text-xs text-slate-400">Jour {draft.sequence_day}</span>
                  )}
                </div>

                {/* Apercu du contenu */}
                <p className="text-sm text-slate-600 whitespace-pre-wrap break-words mb-2">
                  {preview}
                </p>

                {/* Pied : compteur de caracteres + actions */}
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
                  <span className="text-xs text-slate-400">
                    {charCount} caractère{charCount > 1 ? 's' : ''}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={X}
                      disabled={isRowPending}
                      onClick={() => handleReject(draft.draft_id)}
                    >
                      Rejeter
                    </Button>
                    <Button
                      size="sm"
                      icon={Check}
                      loading={isRowPending}
                      disabled={isRowPending}
                      onClick={() => handleApprove(draft.draft_id)}
                    >
                      Approuver
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
