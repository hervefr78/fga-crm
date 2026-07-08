// =============================================================================
// FGA CRM - Contact : carte "Qualification IA" (framework SPICED)
// =============================================================================
// Affiche la grille SPICED (5 dimensions, badge "unknown" sur les vides), le
// routage (fast_track / standard / human_review — jamais de disqualification),
// la prochaine action, et permet de (re)qualifier. Si fast_track : un deal est
// cree automatiquement cote backend (lien affiche).
// =============================================================================

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ClipboardCheck, Sparkles } from 'lucide-react';
import clsx from 'clsx';

import { qualifyContact } from '../../api/client';
import type { Contact } from '../../types';
import { Button } from '../ui';

const ROUTING_META: Record<string, { label: string; cls: string }> = {
  fast_track: { label: 'Fast track', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  standard: { label: 'Standard', cls: 'bg-slate-100 text-slate-600 border-slate-200' },
  human_review: { label: 'À revoir', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
};

const SPICED_LABELS: [string, string][] = [
  ['situation', 'Situation'],
  ['pain', 'Douleur'],
  ['impact', 'Impact'],
  ['critical_event', 'Échéance'],
  ['decision', 'Décision'],
];

export default function ContactQualificationCard({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [createdDealId, setCreatedDealId] = useState<string | null>(null);

  const qualifyMutation = useMutation({
    mutationFn: () => qualifyContact(contact.id),
    onSuccess: (res: { deal_created_id: string | null }) => {
      setErrorMsg(null);
      setCreatedDealId(res.deal_created_id);
      void queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      void queryClient.invalidateQueries({ queryKey: ['contacts'] });
      if (res.deal_created_id) {
        void queryClient.invalidateQueries({ queryKey: ['deals'] });
      }
    },
    onError: () => setErrorMsg('Qualification indisponible. Réessayez plus tard.'),
  });

  const qual = contact.ai_qualification ?? null;
  const routing = contact.ai_routing ? ROUTING_META[contact.ai_routing] : null;
  const spiced = qual?.spiced ?? {};

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <ClipboardCheck className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-sm font-semibold text-slate-800">Qualification IA</span>
        {routing && (
          <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md border text-xs font-medium', routing.cls)}>
            {routing.label}
          </span>
        )}
        <div className="flex-1" />
        <Button
          variant="secondary"
          size="sm"
          icon={Sparkles}
          loading={qualifyMutation.isPending}
          disabled={qualifyMutation.isPending}
          onClick={() => qualifyMutation.mutate()}
        >
          {qualifyMutation.isPending ? 'Analyse…' : qual ? 'Re-qualifier' : 'Qualifier'}
        </Button>
      </div>

      <div className="p-4">
        {!qual ? (
          <p className="text-sm text-slate-400">
            Pas encore qualifié. La qualification SPICED analyse le contexte, la
            douleur et le rôle du contact, puis recommande un routage.
          </p>
        ) : (
          <div className="space-y-3">
            {/* Grille SPICED : 5 dimensions, unknown en badge neutre */}
            <dl className="space-y-1.5">
              {SPICED_LABELS.map(([key, label]) => {
                const dim = spiced[key];
                const isUnknown = !dim || dim.value === 'unknown';
                return (
                  <div key={key} className="flex items-start gap-2 text-sm">
                    <dt className="w-24 shrink-0 text-xs uppercase tracking-wide text-slate-400 pt-0.5">
                      {label}
                    </dt>
                    <dd className="min-w-0">
                      {isUnknown ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] bg-slate-100 text-slate-400">
                          unknown
                        </span>
                      ) : (
                        <span className="text-slate-700">{dim.value}</span>
                      )}
                    </dd>
                  </div>
                );
              })}
            </dl>

            {qual.routing_rationale && (
              <p className="text-xs text-slate-500">{qual.routing_rationale}</p>
            )}

            {qual.next_action && (
              <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                <span className="text-[11px] uppercase tracking-wide text-slate-400">
                  Prochaine action
                </span>
                <p className="text-sm text-slate-700 mt-0.5">{qual.next_action}</p>
              </div>
            )}

          </div>
        )}

        {/* Hors branche `qual` : feedback immediat apres une PREMIERE qualification
            fast_track (le refetch du contact peut arriver un tick plus tard). */}
        {createdDealId && (
          <p className="mt-2 text-xs text-emerald-700">
            Deal créé automatiquement (fast track) —{' '}
            <Link to={`/pipeline/${createdDealId}`} className="underline hover:text-emerald-800">
              ouvrir le deal
            </Link>
          </p>
        )}

        {errorMsg && <p className="mt-2 text-xs text-red-600">{errorMsg}</p>}
      </div>
    </div>
  );
}
