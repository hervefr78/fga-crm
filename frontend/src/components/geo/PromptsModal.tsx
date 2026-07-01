// =============================================================================
// FGA CRM - GEO : modale de gestion des prompts d'une marque (extraite de GEO.tsx)
// =============================================================================

import { Plus, Trash2 } from 'lucide-react';

import type { GeoIntent, GeoPrompt } from '../../types/geo';
import { Button, Modal } from '../ui';
import { GEO_INTENTS } from './geoUtils';

export function PromptsModal({
  open, onClose, canWrite, prompts, text, setText, intent, setIntent, creating, onCreate, onDelete,
}: {
  open: boolean;
  onClose: () => void;
  canWrite: boolean;
  prompts: GeoPrompt[];
  text: string;
  setText: (v: string) => void;
  intent: GeoIntent;
  setIntent: (v: GeoIntent) => void;
  creating: boolean;
  onCreate: () => void;
  onDelete: (promptId: string) => void;
}) {
  if (!canWrite) return null;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Prompts de la marque"
      footer={<Button variant="secondary" onClick={onClose}>Fermer</Button>}
    >
      <div className="space-y-4">
        {prompts.length === 0 ? (
          <p className="text-sm text-slate-500">
            Aucun prompt. Ajoutez-en pour lancer des mesures GEO.
          </p>
        ) : (
          <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg">
            {prompts.map((p) => (
              <div key={p.id} className="flex items-start gap-3 px-3 py-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-700">{p.text}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {p.intent} · {p.country}/{p.language}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onDelete(p.id)}
                  className="p-1 rounded text-slate-400 hover:bg-red-50 hover:text-red-600 flex-shrink-0"
                  title="Supprimer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="border-t border-slate-100 pt-3 space-y-2">
          <label className="block text-xs font-medium text-slate-600">Nouveau prompt</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            placeholder="Ex : Quels sont les meilleurs cabinets de conseil go-to-market ?"
            className="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-700"
          />
          <div className="flex items-center gap-2">
            <select
              value={intent}
              onChange={(e) => setIntent(e.target.value as GeoIntent)}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-700"
            >
              {GEO_INTENTS.map((i) => (
                <option key={i.value} value={i.value}>{i.label}</option>
              ))}
            </select>
            <Button
              variant="primary"
              size="sm"
              icon={Plus}
              loading={creating}
              disabled={!text.trim()}
              onClick={onCreate}
            >
              Ajouter
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
