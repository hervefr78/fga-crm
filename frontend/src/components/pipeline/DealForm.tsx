// =============================================================================
// FGA CRM - Formulaire Deal (creation uniquement)
// =============================================================================

import { useState, FormEvent, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import { Input, Select, Textarea, Button } from '../ui';
import { createDeal, getCompanies, getContacts } from '../../api/client';
import type { PaginatedResponse, Company, Contact } from '../../types';
import { DEAL_STAGES, DEAL_PRIORITIES, DEAL_PRICING_TYPES, PRICING_PERIOD_MONTHS } from '../../types';

interface DealFormProps {
  onSuccess: () => void;
  onCancel: () => void;
  defaultCompanyId?: string;
}

// Label "court" pour le champ recurrent (entre parentheses)
const PRICING_PERIOD_LABEL: Record<string, string> = {
  monthly: 'mensuel',
  quarterly: 'trimestriel',
  biannual: 'semestriel',
  annual: 'annuel',
};

// Formatage simple d'un montant pour l'aide visuelle
function formatAmount(value: number, currency: string): string {
  if (!Number.isFinite(value)) return '—';
  return `${value.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} ${currency}`;
}

export default function DealForm({ onSuccess, onCancel, defaultCompanyId }: DealFormProps) {
  const queryClient = useQueryClient();

  // Etat du formulaire
  const [title, setTitle] = useState('');
  const [stage, setStage] = useState('new');
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('EUR');
  const [probability, setProbability] = useState('0');
  const [priority, setPriority] = useState('medium');
  const [expectedCloseDate, setExpectedCloseDate] = useState('');
  const [companyId, setCompanyId] = useState(defaultCompanyId || '');
  const [contactId, setContactId] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  // Tarification (DC10 : noms exacts du backend)
  const [pricingType, setPricingType] = useState('one_shot');
  const [recurringAmount, setRecurringAmount] = useState('');
  const [commitmentMonths, setCommitmentMonths] = useState('');

  const isRecurring = pricingType !== 'one_shot';

  // Charger les entreprises et contacts pour les dropdowns.
  // Si defaultCompanyId est passe, on filtre les contacts sur l'entreprise (UX cleaner).
  const { data: companiesData } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 100 }],
    queryFn: () => getCompanies({ size: 100 }),
  });

  const contactsParams = defaultCompanyId
    ? { company_id: defaultCompanyId, size: 100 }
    : { size: 100 };

  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', contactsParams],
    queryFn: () => getContacts(contactsParams),
  });

  const companyOptions = (companiesData?.items || []).map((c) => ({
    value: c.id,
    label: c.name,
  }));

  const contactOptions = (contactsData?.items || []).map((c) => ({
    value: c.id,
    label: c.full_name,
  }));

  // Calcul du montant total recurrent (lecture seule, affiche en aide)
  const computedTotal = useMemo(() => {
    if (!isRecurring) return null;
    const recurring = parseFloat(recurringAmount);
    const months = parseInt(commitmentMonths, 10);
    const periodMonths = PRICING_PERIOD_MONTHS[pricingType] || 1;
    if (!Number.isFinite(recurring) || recurring < 0) return null;
    if (!Number.isFinite(months) || months <= 0) return null;
    const totalPeriods = months / periodMonths;
    return recurring * totalPeriods;
  }, [isRecurring, pricingType, recurringAmount, commitmentMonths]);

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createDeal(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['deals'] });
      onSuccess();
    },
    onError: (err: unknown) => {
      const message =
        err instanceof Error ? err.message : 'Une erreur est survenue';
      setError(message);
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (!title.trim()) {
      setError('Le titre du deal est obligatoire');
      return;
    }

    // Validation specifique recurrent : montant unitaire obligatoire (DC1)
    if (isRecurring && !recurringAmount.trim()) {
      setError('Le montant unitaire est obligatoire pour un abonnement');
      return;
    }

    const data: Record<string, unknown> = {
      title: title.trim(),
      stage,
      currency,
      priority,
      probability: parseInt(probability, 10) || 0,
      pricing_type: pricingType,
    };

    if (expectedCloseDate) data.expected_close_date = expectedCloseDate;
    if (companyId) data.company_id = companyId;
    if (contactId) data.contact_id = contactId;
    if (description.trim()) data.description = description.trim();

    if (isRecurring) {
      // Recurrent : on envoie recurring_amount + commitment_months,
      // et on calcule amount total pour les KPI agreges existants.
      if (recurringAmount.trim()) {
        data.recurring_amount = parseFloat(recurringAmount);
      }
      if (commitmentMonths.trim()) {
        data.commitment_months = parseInt(commitmentMonths, 10);
      }
      if (recurringAmount.trim() && commitmentMonths.trim()) {
        const months = PRICING_PERIOD_MONTHS[pricingType] || 1;
        const totalPeriods = parseInt(commitmentMonths, 10) / months;
        data.amount = parseFloat(recurringAmount) * totalPeriods;
      }
    } else {
      // One-shot : amount classique
      if (amount.trim()) data.amount = parseFloat(amount);
    }

    mutation.mutate(data);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Titre */}
      <Input
        label="Titre du deal *"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Contrat SaaS — Acme Corp"
        required
      />

      {/* Stage / Priorite */}
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Stage"
          value={stage}
          onChange={setStage}
          options={[...DEAL_STAGES]}
        />
        <Select
          label="Priorité"
          value={priority}
          onChange={setPriority}
          options={[...DEAL_PRIORITIES]}
        />
      </div>

      {/* Type de tarification */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Type de tarification</label>
        <div className="grid grid-cols-5 gap-2">
          {DEAL_PRICING_TYPES.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setPricingType(p.value)}
              className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                pricingType === p.value
                  ? 'bg-primary-50 border-primary-500 text-primary-700'
                  : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Champs financiers — conditionnels selon pricing_type */}
      {!isRecurring ? (
        // ONE_SHOT : Montant / Devise / Probabilite (comportement initial)
        <div className="grid grid-cols-3 gap-4">
          <Input
            label="Montant"
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="10000"
            min="0"
            step="0.01"
          />
          <Input
            label="Devise"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            placeholder="EUR"
            maxLength={3}
          />
          <Input
            label="Probabilité (%)"
            type="number"
            value={probability}
            onChange={(e) => setProbability(e.target.value)}
            placeholder="50"
            min="0"
            max="100"
          />
        </div>
      ) : (
        // RECURRENT : Montant unitaire + Duree d'engagement + Devise + Probabilite
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label={`Montant unitaire (${PRICING_PERIOD_LABEL[pricingType] || ''}) *`}
              type="number"
              value={recurringAmount}
              onChange={(e) => setRecurringAmount(e.target.value)}
              placeholder="500"
              min="0"
              step="0.01"
              required
            />
            <Input
              label="Durée d'engagement (mois)"
              type="number"
              value={commitmentMonths}
              onChange={(e) => setCommitmentMonths(e.target.value)}
              placeholder="12"
              min="1"
              max="120"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Devise"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              placeholder="EUR"
              maxLength={3}
            />
            <Input
              label="Probabilité (%)"
              type="number"
              value={probability}
              onChange={(e) => setProbability(e.target.value)}
              placeholder="50"
              min="0"
              max="100"
            />
          </div>
          {/* Aide visuelle : valeur totale calculee */}
          {computedTotal !== null && (
            <p className="text-xs text-slate-500">
              Valeur totale du contrat (calcul automatique) :{' '}
              <span className="font-medium text-slate-700">
                {formatAmount(computedTotal, currency)}
              </span>
            </p>
          )}
        </div>
      )}

      {/* Entreprise / Contact */}
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Entreprise"
          value={companyId}
          onChange={setCompanyId}
          options={companyOptions}
          placeholder="Aucune"
        />
        <Select
          label="Contact"
          value={contactId}
          onChange={setContactId}
          options={contactOptions}
          placeholder="Aucun"
        />
      </div>

      {/* Date de cloture prevue */}
      <Input
        label="Date de clôture prévue"
        type="date"
        value={expectedCloseDate}
        onChange={(e) => setExpectedCloseDate(e.target.value)}
      />

      {/* Description */}
      <Textarea
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Notes sur le deal..."
      />

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          Créer le deal
        </Button>
      </div>
    </form>
  );
}
