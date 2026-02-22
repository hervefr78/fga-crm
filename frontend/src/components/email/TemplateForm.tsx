// =============================================================================
// FGA CRM - Formulaire de template email
// =============================================================================

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { createEmailTemplate, updateEmailTemplate } from '../../api/client';
import { Button } from '../ui';
import type { EmailTemplate } from '../../types';
import { TEMPLATE_VARIABLES } from '../../types';

interface TemplateFormProps {
  template?: EmailTemplate;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function TemplateForm({ template, onSuccess, onCancel }: TemplateFormProps) {
  const queryClient = useQueryClient();
  const isEdit = !!template;

  const [name, setName] = useState(template?.name || '');
  const [subject, setSubject] = useState(template?.subject || '');
  const [body, setBody] = useState(template?.body || '');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: () => {
      const data = { name, subject, body };
      return isEdit
        ? updateEmailTemplate(template.id, data)
        : createEmailTemplate(data);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['email-templates'] });
      onSuccess();
    },
    onError: (err: Error) => {
      setError(err.message || 'Erreur lors de la sauvegarde');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('Le nom est requis');
      return;
    }
    if (!subject.trim()) {
      setError('L\'objet est requis');
      return;
    }
    if (!body.trim()) {
      setError('Le contenu est requis');
      return;
    }

    mutation.mutate();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Nom du template */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Nom du template *</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Introduction prospect"
          maxLength={255}
          className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          required
        />
      </div>

      {/* Objet */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Objet *</label>
        <input
          type="text"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Objet de l'email"
          maxLength={500}
          className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          required
        />
      </div>

      {/* Corps */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Contenu *</label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={10}
          maxLength={50000}
          placeholder="Contenu du template..."
          className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-y"
          required
        />
        {/* Variables disponibles */}
        <p className="text-xs text-slate-400 mt-1.5 mb-1">
          Variables disponibles (cliquer pour inserer) :
        </p>
        <div className="flex flex-wrap gap-1.5">
          {TEMPLATE_VARIABLES.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => setBody((prev) => prev + `{{${v.key}}}`)}
              className="px-2 py-0.5 text-xs bg-slate-100 text-slate-500 rounded hover:bg-slate-200 transition-colors"
              title={v.label}
            >
              {`{{${v.key}}}`}
            </button>
          ))}
        </div>
      </div>

      {/* Erreur */}
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {isEdit ? 'Modifier' : 'Creer'}
        </Button>
      </div>
    </form>
  );
}
