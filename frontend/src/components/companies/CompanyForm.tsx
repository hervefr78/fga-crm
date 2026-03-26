// =============================================================================
// FGA CRM - Formulaire Company (creation / edition)
// =============================================================================

import { useState, FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import { Input, Select, Textarea, Button } from '../ui';
import { createCompany, updateCompany } from '../../api/client';
import type { Company } from '../../types';
import { COMPANY_SIZE_RANGES } from '../../types';

interface CompanyFormProps {
  company?: Company;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function CompanyForm({ company, onSuccess, onCancel }: CompanyFormProps) {
  const queryClient = useQueryClient();
  const isEdit = !!company;

  // Etat du formulaire
  const [name, setName] = useState(company?.name || '');
  const [website, setWebsite] = useState(company?.website || '');
  const [industry, setIndustry] = useState(company?.industry || '');
  const [description, setDescription] = useState(company?.description || '');
  const [sizeRange, setSizeRange] = useState(company?.size_range || '');
  const [linkedinUrl, setLinkedinUrl] = useState(company?.linkedin_url || '');
  const [phone, setPhone] = useState(company?.phone || '');
  const [addressLine, setAddressLine] = useState(company?.address_line || '');
  const [postalCode, setPostalCode] = useState(company?.postal_code || '');
  const [city, setCity] = useState(company?.city || '');
  const [country, setCountry] = useState(company?.country || '');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      isEdit ? updateCompany(company.id, data) : createCompany(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
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

    if (!name.trim()) {
      setError("Le nom de l'entreprise est obligatoire");
      return;
    }

    const data: Record<string, unknown> = {
      name: name.trim(),
    };

    if (website.trim()) data.website = website.trim();
    if (industry.trim()) data.industry = industry.trim();
    if (description.trim()) data.description = description.trim();
    if (sizeRange) data.size_range = sizeRange;
    if (linkedinUrl.trim()) data.linkedin_url = linkedinUrl.trim();
    if (phone.trim()) data.phone = phone.trim();
    if (addressLine.trim()) data.address_line = addressLine.trim();
    if (postalCode.trim()) data.postal_code = postalCode.trim();
    if (city.trim()) data.city = city.trim();
    if (country.trim()) data.country = country.trim();

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

      {/* Nom */}
      <Input
        label="Nom de l'entreprise *"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Acme Corp"
        required
      />

      {/* Site web */}
      <Input
        label="Site web"
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        placeholder="https://acme.com"
      />

      {/* Secteur / Taille */}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Secteur d'activité"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          placeholder="SaaS, Fintech..."
        />
        <Select
          label="Taille"
          value={sizeRange}
          onChange={setSizeRange}
          options={[...COMPANY_SIZE_RANGES]}
          placeholder="Sélectionner..."
        />
      </div>

      {/* Adresse */}
      <Input
        label="Adresse"
        value={addressLine}
        onChange={(e) => setAddressLine(e.target.value)}
        placeholder="12 rue de la Paix"
      />
      <div className="grid grid-cols-3 gap-4">
        <Input
          label="Code postal"
          value={postalCode}
          onChange={(e) => setPostalCode(e.target.value)}
          placeholder="75002"
        />
        <Input
          label="Ville"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="Paris"
        />
        <Input
          label="Pays"
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          placeholder="France"
        />
      </div>

      {/* Telephone / LinkedIn */}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Téléphone"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+33 1 23 45 67 89"
        />
        <Input
          label="LinkedIn"
          value={linkedinUrl}
          onChange={(e) => setLinkedinUrl(e.target.value)}
          placeholder="https://linkedin.com/company/..."
        />
      </div>

      {/* Description */}
      <Textarea
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description de l'entreprise..."
      />

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {isEdit ? 'Enregistrer' : "Créer l'entreprise"}
        </Button>
      </div>
    </form>
  );
}
