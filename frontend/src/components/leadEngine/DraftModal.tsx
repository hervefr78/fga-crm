// =============================================================================
// FGA CRM - Lead Engine : modale du draft d'outreach (validation humaine)
// =============================================================================
// Le draft n'est JAMAIS envoye automatiquement (garde-fou §2.4 de la vision) :
// cette modale le presente pour relecture, l'envoi passe par le composer email
// (editable avant envoi).
// =============================================================================

import { PenLine } from 'lucide-react';

import { Button, Modal } from '../ui';
import type { LeadSignalDraft } from '../../types/leadEngine';

interface DraftModalProps {
  open: boolean;
  draft: LeadSignalDraft | null;
  onClose: () => void;
  onCompose: () => void;   // ouvre le composer pre-rempli (envoi valide par l'humain)
}

export default function DraftModal({ open, draft, onClose, onCompose }: DraftModalProps) {
  if (!draft) return null;
  return (
    <Modal open={open} onClose={onClose} title="Draft d'outreach — à valider" size="lg">
      <div className="space-y-4">
        <div className="text-sm text-slate-500">
          Pour <span className="font-medium text-slate-700">{draft.contact_name}</span>
          {' '}({draft.contact_email})
        </div>

        <div>
          <p className="text-xs font-medium text-slate-400 mb-1">Objet</p>
          <p className="text-sm text-slate-800 border border-slate-200 rounded-lg px-3 py-2 bg-slate-50">
            {draft.subject}
          </p>
        </div>

        <div>
          <p className="text-xs font-medium text-slate-400 mb-1">Message</p>
          <p className="text-sm text-slate-700 border border-slate-200 rounded-lg px-3 py-2 bg-slate-50 whitespace-pre-wrap">
            {draft.body}
          </p>
        </div>

        <p className="text-xs text-slate-400">
          Angle : {draft.angle_rationale}
          {draft.prompt_version && ` · ${draft.prompt_version}`}
        </p>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose}>Fermer</Button>
          <Button icon={PenLine} onClick={onCompose}>
            Relire et envoyer (composer)
          </Button>
        </div>
      </div>
    </Modal>
  );
}
