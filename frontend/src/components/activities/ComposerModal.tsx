// =============================================================================
// FGA CRM - ComposerModal : composer multi-canal pour creer une activite
// =============================================================================
//
// Composant partage par les pages detail (DC8). Permet de creer rapidement
// une activite (note / email log / appel / RDV) depuis une fiche
// Company / Contact / Deal.
//
// Note : pour un envoi d'email reel, utiliser ComposeModal (email/) qui
// passe par /emails/send. Ici on ne fait QUE creer un Activity (log).
// =============================================================================

import { useState, FormEvent, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertCircle } from 'lucide-react';

import { Modal, Button, Input, Textarea } from '../ui';
import { createActivity } from '../../api/client';

export type ComposerChannel = 'note' | 'email' | 'call' | 'meeting';

const CHANNEL_LABELS: Record<ComposerChannel, string> = {
  note: 'Note',
  email: 'Email',
  call: 'Appel',
  meeting: 'RDV',
};

const CHANNEL_DEFAULTS: Record<ComposerChannel, { subject: string; placeholder: string }> = {
  note: { subject: '', placeholder: 'Ajouter une note rapide...' },
  email: { subject: 'Email envoye', placeholder: 'Resume de l\'email envoye...' },
  call: { subject: 'Appel pris en note', placeholder: 'Resume de l\'appel...' },
  meeting: { subject: 'RDV', placeholder: 'Notes de RDV (date, participants, decisions)...' },
};

interface ComposerModalProps {
  open: boolean;
  onClose: () => void;
  initialChannel?: ComposerChannel;
  // Une seule des trois cles doit etre fournie (la fiche source)
  contactId?: string;
  companyId?: string;
  dealId?: string;
}

export default function ComposerModal({
  open,
  onClose,
  initialChannel = 'note',
  contactId,
  companyId,
  dealId,
}: ComposerModalProps) {
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState<ComposerChannel>(initialChannel);
  const [subject, setSubject] = useState('');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');

  // Reset au switch de canal ou a l'ouverture
  useEffect(() => {
    if (!open) return;
    setChannel(initialChannel);
    setSubject(CHANNEL_DEFAULTS[initialChannel].subject);
    setContent('');
    setError('');
  }, [open, initialChannel]);

  // Quand on switche de canal manuellement, on reapplique le subject par defaut
  // uniquement si le user n'a pas saisi de subject custom (UX intuitive).
  const switchChannel = (next: ComposerChannel) => {
    setChannel(next);
    setSubject((prev) => {
      const wasDefault = Object.values(CHANNEL_DEFAULTS).some((d) => d.subject === prev);
      return wasDefault || prev === '' ? CHANNEL_DEFAULTS[next].subject : prev;
    });
  };

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createActivity(data),
    onSuccess: () => {
      // Invalidate les listes d'activites de chaque entite liee
      if (contactId) {
        void queryClient.invalidateQueries({ queryKey: ['activities', { contact_id: contactId }] });
      }
      if (companyId) {
        void queryClient.invalidateQueries({ queryKey: ['activities', { company_id: companyId }] });
      }
      if (dealId) {
        void queryClient.invalidateQueries({ queryKey: ['activities', { deal_id: dealId }] });
      }
      onClose();
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Une erreur est survenue';
      setError(message);
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation minimale (DC1) : au moins un subject ou un content
    if (!subject.trim() && !content.trim()) {
      setError('Renseigne au moins un sujet ou un contenu.');
      return;
    }

    const data: Record<string, unknown> = {
      type: channel,
      subject: subject.trim() || undefined,
      content: content.trim() || undefined,
    };
    if (contactId) data.contact_id = contactId;
    if (companyId) data.company_id = companyId;
    if (dealId) data.deal_id = dealId;

    mutation.mutate(data);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nouvelle activite"
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Selecteur canal */}
        <div className="flex gap-1 border border-slate-200 rounded-lg p-1 bg-slate-50">
          {(Object.keys(CHANNEL_LABELS) as ComposerChannel[]).map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => switchChannel(c)}
              className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                channel === c
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {CHANNEL_LABELS[c]}
            </button>
          ))}
        </div>

        {/* Erreur (DC7 — formulaire reste visible) */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-3 py-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <Input
          label="Sujet"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder={channel === 'note' ? '(optionnel)' : 'Sujet'}
          maxLength={500}
        />

        <Textarea
          label="Contenu"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={CHANNEL_DEFAULTS[channel].placeholder}
          rows={5}
        />

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            Publier
          </Button>
        </div>
      </form>
    </Modal>
  );
}
