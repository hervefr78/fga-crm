// =============================================================================
// FGA CRM - Formulaire Contact (creation / edition)
// =============================================================================

import { useState, FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import { Input, Select, Textarea, Button } from '../ui';
import { createContact, updateContact, getCompanies } from '../../api/client';
import type { Contact, PaginatedResponse, Company } from '../../types';
import { CONTACT_STATUSES, JOB_LEVELS } from '../../types';

interface ContactFormProps {
  contact?: Contact;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function ContactForm({ contact, onSuccess, onCancel }: ContactFormProps) {
  const queryClient = useQueryClient();
  const isEdit = !!contact;

  // Etat du formulaire
  const [firstName, setFirstName] = useState(contact?.first_name || '');
  const [lastName, setLastName] = useState(contact?.last_name || '');
  const [email, setEmail] = useState(contact?.email || '');
  const [phone, setPhone] = useState(contact?.phone || '');
  const [title, setTitle] = useState(contact?.title || '');
  const [jobLevel, setJobLevel] = useState(contact?.job_level || '');
  const [department, setDepartment] = useState(contact?.department || '');
  const [linkedinUrl, setLinkedinUrl] = useState(contact?.linkedin_url || '');
  const [companyId, setCompanyId] = useState(contact?.company_id || '');
  const [source, setSource] = useState(contact?.source || '');
  const [status, setStatus] = useState(contact?.status || 'new');
  const [error, setError] = useState('');

  // Charger les entreprises pour le dropdown (cap a 100 pour Sprint 1)
  const { data: companiesData } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 100 }],
    queryFn: () => getCompanies({ size: 100 }),
  });

  const companyOptions = (companiesData?.items || []).map((c) => ({
    value: c.id,
    label: c.name,
  }));

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      isEdit ? updateContact(contact.id, data) : createContact(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contacts'] });
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
    if (!firstName.trim() || !lastName.trim()) {
      setError('Le prénom et le nom sont obligatoires');
      return;
    }

    const data: Record<string, unknown> = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      status,
    };

    // Ajouter les champs optionnels non vides
    if (email.trim()) data.email = email.trim();
    if (phone.trim()) data.phone = phone.trim();
    if (title.trim()) data.title = title.trim();
    if (jobLevel) data.job_level = jobLevel;
    if (department.trim()) data.department = department.trim();
    if (linkedinUrl.trim()) data.linkedin_url = linkedinUrl.trim();
    if (companyId) data.company_id = companyId;
    if (source.trim()) data.source = source.trim();

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

      {/* Prenom / Nom */}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Prénom *"
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          placeholder="Jean"
          required
        />
        <Input
          label="Nom *"
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          placeholder="Dupont"
          required
        />
      </div>

      {/* Email / Telephone */}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jean@entreprise.com"
        />
        <Input
          label="Téléphone"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+33 6 12 34 56 78"
        />
      </div>

      {/* Titre / Niveau */}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Titre"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="CEO, VP Sales..."
        />
        <Select
          label="Niveau"
          value={jobLevel}
          onChange={setJobLevel}
          options={[...JOB_LEVELS]}
          placeholder="Sélectionner..."
        />
      </div>

      {/* Departement / Entreprise */}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Département"
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          placeholder="Sales, Marketing..."
        />
        <Select
          label="Entreprise"
          value={companyId}
          onChange={setCompanyId}
          options={companyOptions}
          placeholder="Aucune"
        />
      </div>

      {/* Statut / Source */}
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Statut"
          value={status}
          onChange={setStatus}
          options={[...CONTACT_STATUSES]}
        />
        <Input
          label="Source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="LinkedIn, site web..."
        />
      </div>

      {/* LinkedIn */}
      <Input
        label="Profil LinkedIn"
        value={linkedinUrl}
        onChange={(e) => setLinkedinUrl(e.target.value)}
        placeholder="https://linkedin.com/in/..."
      />

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {isEdit ? 'Enregistrer' : 'Créer le contact'}
        </Button>
      </div>
    </form>
  );
}
