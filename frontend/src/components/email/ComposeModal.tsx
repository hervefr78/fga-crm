// =============================================================================
// FGA CRM - Modal de composition d'email
// =============================================================================

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Send } from 'lucide-react';

import { sendEmail, getEmailTemplates, getContacts } from '../../api/client';
import { Button, Modal } from '../ui';
import type {
  Contact,
  EmailTemplate,
  PaginatedResponse,
} from '../../types';
import { TEMPLATE_VARIABLES } from '../../types';

interface ComposeModalProps {
  open: boolean;
  onClose: () => void;
  prefilledContact?: Contact;
}

export default function ComposeModal({ open, onClose, prefilledContact }: ComposeModalProps) {
  const queryClient = useQueryClient();

  // Champs du formulaire
  const [toEmail, setToEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [contactId, setContactId] = useState<string>('');
  const [templateId, setTemplateId] = useState<string>('');
  const [error, setError] = useState('');

  // Charger les contacts (pour le select)
  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', { size: 200 }],
    queryFn: () => getContacts({ size: 200 }),
    enabled: open && !prefilledContact,
  });

  // Charger les templates
  const { data: templatesData } = useQuery<PaginatedResponse<EmailTemplate>>({
    queryKey: ['email-templates', { size: 100 }],
    queryFn: () => getEmailTemplates({ size: 100 }),
    enabled: open,
  });

  // Pre-remplir si contact fourni
  useEffect(() => {
    if (open && prefilledContact) {
      setContactId(prefilledContact.id);
      setToEmail(prefilledContact.email || '');
    }
  }, [open, prefilledContact]);

  // Reset a la fermeture
  useEffect(() => {
    if (!open) {
      setToEmail('');
      setSubject('');
      setBody('');
      setContactId('');
      setTemplateId('');
      setError('');
    }
  }, [open]);

  // Appliquer un template
  const handleTemplateChange = (id: string) => {
    setTemplateId(id);
    if (!id) return;
    const template = templatesData?.items.find((t) => t.id === id);
    if (template) {
      setSubject(template.subject);
      setBody(template.body);
    }
  };

  // Selection d'un contact → remplir l'email
  const handleContactChange = (id: string) => {
    setContactId(id);
    if (!id) {
      setToEmail('');
      return;
    }
    const contact = contactsData?.items.find((c) => c.id === id);
    if (contact?.email) {
      setToEmail(contact.email);
    }
  };

  // Mutation envoi
  const mutation = useMutation({
    mutationFn: () =>
      sendEmail({
        to_email: toEmail,
        subject,
        body,
        ...(contactId ? { contact_id: contactId } : {}),
        ...(templateId ? { template_id: templateId } : {}),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['emails'] });
      void queryClient.invalidateQueries({ queryKey: ['activities'] });
      onClose();
    },
    onError: (err: Error) => {
      setError(err.message || 'Erreur lors de l\'envoi');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!toEmail.trim()) {
      setError('L\'adresse email est requise');
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

  const templates = templatesData?.items || [];
  const contacts = contactsData?.items || [];

  return (
    <Modal open={open} onClose={onClose} title="Nouveau message" size="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Selection du contact (sauf si prefilled) */}
        {!prefilledContact && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Contact</label>
            <select
              value={contactId}
              onChange={(e) => handleContactChange(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="">Saisie manuelle</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} {c.email ? `(${c.email})` : ''}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Adresse email */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Destinataire *</label>
          <input
            type="email"
            value={toEmail}
            onChange={(e) => setToEmail(e.target.value)}
            placeholder="email@exemple.com"
            className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            required
          />
        </div>

        {/* Template */}
        {templates.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Template</label>
            <select
              value={templateId}
              onChange={(e) => handleTemplateChange(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="">Aucun template</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        )}

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
          <label className="block text-sm font-medium text-slate-700 mb-1">Message *</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={8}
            maxLength={50000}
            placeholder="Contenu de l'email..."
            className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-y"
            required
          />
          {/* Variables disponibles */}
          <div className="mt-1.5 flex flex-wrap gap-1.5">
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
          <Button variant="secondary" type="button" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" icon={Send} loading={mutation.isPending}>
            Envoyer
          </Button>
        </div>
      </form>
    </Modal>
  );
}
