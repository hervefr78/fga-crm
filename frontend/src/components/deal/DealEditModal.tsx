// =============================================================================
// FGA CRM - Modal d'edition complete d'un Deal (pricing + cross-fields)
// Extrait VERBATIM de DealDetail.tsx (refactor C5) — logique inchangee.
// DC8 : la logique reste localisee a la fiche mais factorisee dans un composant
// pour preserver la lisibilite.
// =============================================================================

import { useState, useEffect, FormEvent } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { AlertCircle, X } from 'lucide-react';
import clsx from 'clsx';

import { updateDeal, getCompanies, getContacts } from '../../api/client';
import type { Deal, Company, Contact, PaginatedResponse } from '../../types';
import {
  DEAL_STAGES, DEAL_PRIORITIES, DEAL_PRICING_TYPES, PRICING_PERIOD_MONTHS,
} from '../../types';
import { Button, Modal } from '../ui';
import { PRICING_PERIOD_LABEL } from './dealUtils';

interface EditForm {
  title: string;
  stage: string;
  amount: string;
  currency: string;
  probability: string;
  priority: string;
  expected_close_date: string;
  company_id: string;
  contact_id: string;
  description: string;
  pricing_type: string;
  recurring_amount: string;
  commitment_months: string;
  loss_reason: string;
}

export default function DealEditModal({
  open, onClose, deal, onSaved,
}: {
  open: boolean;
  onClose: () => void;
  deal: Deal;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<EditForm>(() => buildInitialForm(deal));
  const [error, setError] = useState<string | null>(null);

  // Re-init le form a chaque ouverture (le deal peut avoir change suite a une autre action)
  useEffect(() => {
    if (open) {
      setForm(buildInitialForm(deal));
      setError(null);
    }
  }, [open, deal]);

  const { data: companiesData } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 100 }],
    queryFn: () => getCompanies({ size: 100 }),
    enabled: open,
  });

  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', { size: 100 }],
    queryFn: () => getContacts({ size: 100 }),
    enabled: open,
  });

  const editMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateDeal(deal.id, data),
    onSuccess: () => onSaved(),
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Une erreur est survenue';
      setError(message);
    },
  });

  const companyOptions = (companiesData?.items ?? []).map((c) => ({ value: c.id, label: c.name }));
  const contactOptions = (contactsData?.items ?? []).map((c) => ({ value: c.id, label: c.full_name }));

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation cross-field (DC8 — meme regle que DealForm.tsx)
    if (form.pricing_type !== 'one_shot' && !form.recurring_amount.trim()) {
      setError('Le montant unitaire est obligatoire pour un abonnement.');
      return;
    }

    const data: Record<string, unknown> = {
      title: form.title.trim(),
      stage: form.stage,
      currency: form.currency,
      priority: form.priority,
      probability: parseInt(form.probability, 10) || 0,
      pricing_type: form.pricing_type,
    };
    if (form.expected_close_date) data.expected_close_date = form.expected_close_date;
    data.company_id = form.company_id || null;
    data.contact_id = form.contact_id || null;
    data.description = form.description.trim() || null;

    // loss_reason : conserve uniquement si stage='lost' (sinon on reset cote backend)
    if (form.stage === 'lost') {
      data.loss_reason = form.loss_reason.trim() || null;
    } else {
      data.loss_reason = null;
    }

    // Tarification
    if (form.pricing_type === 'one_shot') {
      data.recurring_amount = null;
      data.commitment_months = null;
      if (form.amount.trim()) data.amount = parseFloat(form.amount);
    } else {
      if (form.recurring_amount.trim()) {
        data.recurring_amount = parseFloat(form.recurring_amount);
      }
      if (form.commitment_months.trim()) {
        data.commitment_months = parseInt(form.commitment_months, 10);
      }
      // Recalcul du montant total = recurring * (commit / period_months)
      if (form.recurring_amount.trim() && form.commitment_months.trim()) {
        const months = PRICING_PERIOD_MONTHS[form.pricing_type] || 1;
        const totalPeriods = parseInt(form.commitment_months, 10) / months;
        data.amount = parseFloat(form.recurring_amount) * totalPeriods;
      }
    }

    editMutation.mutate(data);
  };

  return (
    <Modal open={open} onClose={onClose} title="Modifier le deal" size="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Titre + stage + priorite */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-3">
            <label className="block text-sm font-medium text-slate-700 mb-1">Titre</label>
            <input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Stage</label>
            <select
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {DEAL_STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Priorite</label>
            <select
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {DEAL_PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Probabilite (%)</label>
            <input
              type="number" min={0} max={100}
              value={form.probability}
              onChange={(e) => setForm({ ...form, probability: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Erreur */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-3 py-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Pricing type */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Type de tarification</label>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {DEAL_PRICING_TYPES.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setForm({ ...form, pricing_type: p.value })}
                className={clsx(
                  'px-3 py-2 text-xs font-medium rounded-lg border transition-colors',
                  form.pricing_type === p.value
                    ? 'bg-primary-50 border-primary-500 text-primary-700'
                    : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300',
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Montants conditionnels */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {form.pricing_type === 'one_shot' ? (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Montant</label>
              <input
                type="number" min={0} step={0.01}
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="0"
              />
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Montant {PRICING_PERIOD_LABEL[form.pricing_type] ?? ''}
                </label>
                <input
                  type="number" min={0} step={0.01}
                  value={form.recurring_amount}
                  onChange={(e) => setForm({ ...form, recurring_amount: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Engagement (mois)</label>
                <input
                  type="number" min={1} max={120}
                  value={form.commitment_months}
                  onChange={(e) => setForm({ ...form, commitment_months: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="12"
                />
              </div>
            </>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Devise</label>
            <input
              maxLength={3}
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 uppercase"
            />
          </div>
        </div>

        {/* Date + entreprise + contact */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Date de cloture prevue</label>
            <input
              type="date"
              value={form.expected_close_date}
              onChange={(e) => setForm({ ...form, expected_close_date: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Entreprise</label>
            <select
              value={form.company_id}
              onChange={(e) => setForm({ ...form, company_id: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Aucune</option>
              {companyOptions.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Contact</label>
            <select
              value={form.contact_id}
              onChange={(e) => setForm({ ...form, contact_id: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Aucun</option>
              {contactOptions.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[80px]"
            placeholder="Notes sur le deal..."
          />
        </div>

        {/* Loss reason — visible uniquement si stage='lost' */}
        {form.stage === 'lost' && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Raison de la perte</label>
            <textarea
              value={form.loss_reason}
              onChange={(e) => setForm({ ...form, loss_reason: e.target.value })}
              maxLength={255}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[60px]"
              placeholder="Ex : Budget non valide, choix d'un concurrent..."
            />
            <p className="text-xs text-slate-400 mt-1">{form.loss_reason.length}/255 caracteres</p>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose} icon={X}>Annuler</Button>
          <Button type="submit" loading={editMutation.isPending}>Enregistrer</Button>
        </div>
      </form>
    </Modal>
  );
}

function buildInitialForm(deal: Deal): EditForm {
  return {
    title: deal.title,
    stage: deal.stage,
    amount: deal.amount?.toString() ?? '',
    currency: deal.currency,
    probability: deal.probability?.toString() ?? '0',
    priority: deal.priority,
    expected_close_date: deal.expected_close_date ?? '',
    company_id: deal.company_id ?? '',
    contact_id: deal.contact_id ?? '',
    description: deal.description ?? '',
    pricing_type: deal.pricing_type,
    recurring_amount: deal.recurring_amount?.toString() ?? '',
    commitment_months: deal.commitment_months?.toString() ?? '',
    loss_reason: deal.loss_reason ?? '',
  };
}
