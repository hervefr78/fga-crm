// =============================================================================
// FGA CRM - Formulaire Deal (creation / edition)
// =============================================================================

import { useState, FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import { Input, Select, Textarea, Button } from '../ui';
import { createDeal, updateDeal, getCompanies, getContacts } from '../../api/client';
import type { Deal, PaginatedResponse, Company, Contact } from '../../types';
import { DEAL_STAGES, DEAL_PRIORITIES } from '../../types';

interface DealFormProps {
  deal?: Deal;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function DealForm({ deal, onSuccess, onCancel }: DealFormProps) {
  const queryClient = useQueryClient();
  const isEdit = !!deal;

  // Etat du formulaire
  const [title, setTitle] = useState(deal?.title || '');
  const [stage, setStage] = useState(deal?.stage || 'new');
  const [amount, setAmount] = useState(deal?.amount?.toString() || '');
  const [currency, setCurrency] = useState(deal?.currency || 'EUR');
  const [probability, setProbability] = useState(deal?.probability?.toString() || '0');
  const [priority, setPriority] = useState(deal?.priority || 'medium');
  const [expectedCloseDate, setExpectedCloseDate] = useState(deal?.expected_close_date || '');
  const [companyId, setCompanyId] = useState(deal?.company_id || '');
  const [contactId, setContactId] = useState(deal?.contact_id || '');
  const [description, setDescription] = useState(deal?.description || '');
  const [error, setError] = useState('');

  // Charger les entreprises et contacts pour les dropdowns
  const { data: companiesData } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 100 }],
    queryFn: () => getCompanies({ size: 100 }),
  });

  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', { size: 100 }],
    queryFn: () => getContacts({ size: 100 }),
  });

  const companyOptions = (companiesData?.items || []).map((c) => ({
    value: c.id,
    label: c.name,
  }));

  const contactOptions = (contactsData?.items || []).map((c) => ({
    value: c.id,
    label: c.full_name,
  }));

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      isEdit ? updateDeal(deal.id, data) : createDeal(data),
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

    const data: Record<string, unknown> = {
      title: title.trim(),
      stage,
      currency,
      priority,
      probability: parseInt(probability, 10) || 0,
    };

    if (amount.trim()) data.amount = parseFloat(amount);
    if (expectedCloseDate) data.expected_close_date = expectedCloseDate;
    if (companyId) data.company_id = companyId;
    if (contactId) data.contact_id = contactId;
    if (description.trim()) data.description = description.trim();

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

      {/* Montant / Devise / Probabilite */}
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
          {isEdit ? 'Enregistrer' : 'Créer le deal'}
        </Button>
      </div>
    </form>
  );
}
