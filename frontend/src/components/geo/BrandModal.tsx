// =============================================================================
// FGA CRM - GEO : modale de creation de marque (extraite de GEO.tsx)
// =============================================================================

import { Plus } from 'lucide-react';

import { Button, Modal } from '../ui';
import { slugify } from './geoUtils';

export function BrandModal({
  open, onClose, canWrite, name, setName, aliases, setAliases, submitting, onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  canWrite: boolean;
  name: string;
  setName: (v: string) => void;
  aliases: string;
  setAliases: (v: string) => void;
  submitting: boolean;
  onSubmit: () => void;
}) {
  if (!canWrite) return null;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ajouter une marque"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button
            variant="primary"
            icon={Plus}
            loading={submitting}
            disabled={!name.trim()}
            onClick={onSubmit}
          >
            Creer
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Nom de la marque</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex : Fast Growth Advisor"
            className="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-700"
          />
          {name.trim() && (
            <p className="text-xs text-slate-400 mt-1">
              slug : <span className="tabular-nums">{slugify(name)}</span>
            </p>
          )}
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">
            Aliases (variantes, separes par des virgules)
          </label>
          <input
            type="text"
            value={aliases}
            onChange={(e) => setAliases(e.target.value)}
            placeholder="FGA, fast-growth"
            className="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-700"
          />
        </div>
        <p className="text-xs text-slate-400">
          Enregistree comme marque « possedee » (suivi de votre visibilite generative).
        </p>
      </div>
    </Modal>
  );
}
