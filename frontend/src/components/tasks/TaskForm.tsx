// =============================================================================
// FGA CRM - Formulaire Tache (creation / edition)
// =============================================================================

import { useState, FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import { Input, Select, Textarea, Button } from '../ui';
import { createTask, updateTask, getContacts, getDeals } from '../../api/client';
import type { Task, PaginatedResponse, Contact, Deal } from '../../types';
import { TASK_TYPES, TASK_PRIORITIES } from '../../types';

interface TaskFormProps {
  task?: Task;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function TaskForm({ task, onSuccess, onCancel }: TaskFormProps) {
  const queryClient = useQueryClient();
  const isEdit = !!task;

  // Etat du formulaire
  const [title, setTitle] = useState(task?.title || '');
  const [description, setDescription] = useState(task?.description || '');
  const [type, setType] = useState(task?.type || 'todo');
  const [priority, setPriority] = useState(task?.priority || 'medium');
  const [dueDate, setDueDate] = useState(task?.due_date?.split('T')[0] || '');
  const [contactId, setContactId] = useState(task?.contact_id || '');
  const [dealId, setDealId] = useState(task?.deal_id || '');
  const [error, setError] = useState('');

  // Charger les contacts et deals pour les dropdowns (cap a 100)
  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', { size: 100 }],
    queryFn: () => getContacts({ size: 100 }),
  });

  const { data: dealsData } = useQuery<PaginatedResponse<Deal>>({
    queryKey: ['deals', { size: 100 }],
    queryFn: () => getDeals({ size: 100 }),
  });

  const contactOptions = (contactsData?.items || []).map((c) => ({
    value: c.id,
    label: c.full_name,
  }));

  const dealOptions = (dealsData?.items || []).map((d) => ({
    value: d.id,
    label: d.title,
  }));

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      isEdit ? updateTask(task.id, data) : createTask(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks'] });
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
    if (!title.trim()) {
      setError('Le titre est obligatoire');
      return;
    }

    const data: Record<string, unknown> = {
      title: title.trim(),
      type,
      priority,
    };

    // Ajouter les champs optionnels non vides
    if (description.trim()) data.description = description.trim();
    if (dueDate) data.due_date = dueDate;
    if (contactId) data.contact_id = contactId;
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

      {/* Titre */}
      <Input
        label="Titre *"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Appeler le prospect, envoyer la proposition..."
        required
      />

      {/* Type / Priorite */}
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Type"
          value={type}
          onChange={setType}
          options={[...TASK_TYPES]}
        />
        <Select
          label="Priorité"
          value={priority}
          onChange={setPriority}
          options={[...TASK_PRIORITIES]}
        />
      </div>

      {/* Date d'echeance */}
      <Input
        label="Date d'échéance"
        type="date"
        value={dueDate}
        onChange={(e) => setDueDate(e.target.value)}
      />

      {/* Contact / Deal */}
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Contact"
          value={contactId}
          onChange={setContactId}
          options={contactOptions}
          placeholder="Aucun"
        />
        <Select
          label="Deal"
          value={dealId}
          onChange={setDealId}
          options={dealOptions}
          placeholder="Aucun"
        />
      </div>

      {/* Description */}
      <Textarea
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Details sur la tache..."
      />

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {isEdit ? 'Enregistrer' : 'Créer la tâche'}
        </Button>
      </div>
    </form>
  );
}
