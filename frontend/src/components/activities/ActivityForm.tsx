// =============================================================================
// FGA CRM - Formulaire Activite (creation / edition)
// =============================================================================

import { useState, FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import { Input, Select, Textarea, Button } from '../ui';
import {
  createActivity,
  updateActivity,
  getContacts,
  getCompanies,
  getDeals,
} from '../../api/client';
import type { Activity, PaginatedResponse, Contact, Company, Deal } from '../../types';
import { ACTIVITY_TYPES } from '../../types';

interface ActivityFormProps {
  activity?: Activity;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function ActivityForm({ activity, onSuccess, onCancel }: ActivityFormProps) {
  const queryClient = useQueryClient();
  const isEdit = !!activity;

  // Etat du formulaire
  const [type, setType] = useState(activity?.type || 'note');
  const [subject, setSubject] = useState(activity?.subject || '');
  const [content, setContent] = useState(activity?.content || '');
  const [contactId, setContactId] = useState(activity?.contact_id || '');
  const [companyId, setCompanyId] = useState(activity?.company_id || '');
  const [dealId, setDealId] = useState(activity?.deal_id || '');
  const [error, setError] = useState('');

  // Charger les entites pour les dropdowns (cap a 100)
  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', { size: 100 }],
    queryFn: () => getContacts({ size: 100 }),
  });

  const { data: companiesData } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 100 }],
    queryFn: () => getCompanies({ size: 100 }),
  });

  const { data: dealsData } = useQuery<PaginatedResponse<Deal>>({
    queryKey: ['deals', { size: 100 }],
    queryFn: () => getDeals({ size: 100 }),
  });

  const contactOptions = (contactsData?.items || []).map((c) => ({
    value: c.id,
    label: c.full_name,
  }));

  const companyOptions = (companiesData?.items || []).map((c) => ({
    value: c.id,
    label: c.name,
  }));

  const dealOptions = (dealsData?.items || []).map((d) => ({
    value: d.id,
    label: d.title,
  }));

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      isEdit ? updateActivity(activity.id, data) : createActivity(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['activities'] });
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

    // Validation client minimale
    if (!type) {
      setError('Le type est obligatoire');
      return;
    }

    const data: Record<string, unknown> = { type };

    // Ajouter les champs optionnels non vides
    if (subject.trim()) data.subject = subject.trim();
    if (content.trim()) data.content = content.trim();
    if (contactId) data.contact_id = contactId;
    if (companyId) data.company_id = companyId;
    if (dealId) data.deal_id = dealId;

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

      {/* Type */}
      <Select
        label="Type *"
        value={type}
        onChange={setType}
        options={[...ACTIVITY_TYPES]}
      />

      {/* Sujet */}
      <Input
        label="Sujet"
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Appel de prospection, reunion de suivi..."
      />

      {/* Contact / Entreprise */}
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Contact"
          value={contactId}
          onChange={setContactId}
          options={contactOptions}
          placeholder="Aucun"
        />
        <Select
          label="Entreprise"
          value={companyId}
          onChange={setCompanyId}
          options={companyOptions}
          placeholder="Aucune"
        />
      </div>

      {/* Deal */}
      <Select
        label="Deal"
        value={dealId}
        onChange={setDealId}
        options={dealOptions}
        placeholder="Aucun"
      />

      {/* Contenu */}
      <Textarea
        label="Contenu"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Details de l'activite..."
      />

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {isEdit ? 'Enregistrer' : 'Créer l\'activité'}
        </Button>
      </div>
    </form>
  );
}
