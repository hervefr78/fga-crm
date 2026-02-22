// =============================================================================
// FGA CRM - Modal d'import CSV multi-etapes
// =============================================================================

import { useState, useCallback } from 'react';
import Papa from 'papaparse';
import { Upload, ArrowRight, CheckCircle, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

import { Modal, Button, Select } from '../ui';
import { importContacts, importCompanies } from '../../api/client';
import type { ImportResult, ImportRowError } from '../../types';
import type { CsvColumn } from '../../utils/csv';

// ---------- Constantes ----------

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB (DC1)
const MAX_ROWS = 1000; // DC1

// ---------- Types ----------

interface CsvImportModalProps {
  open: boolean;
  onClose: () => void;
  entity: 'contacts' | 'companies';
  columns: CsvColumn[];
  onSuccess: () => void;
}

type Step = 'upload' | 'mapping' | 'preview' | 'result';

// ---------- Composant ----------

export default function CsvImportModal({ open, onClose, entity, columns, onSuccess }: CsvImportModalProps) {
  const [step, setStep] = useState<Step>('upload');
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [csvRows, setCsvRows] = useState<Record<string, string>[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Reinitialiser quand on ferme
  const handleClose = useCallback(() => {
    setStep('upload');
    setCsvHeaders([]);
    setCsvRows([]);
    setMapping({});
    setResult(null);
    setError(null);
    setLoading(false);
    onClose();
  }, [onClose]);

  // Etape 1 : Upload et parse
  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);

    if (file.size > MAX_FILE_SIZE) {
      setError('Fichier trop volumineux (max 5 MB)');
      return;
    }

    if (!file.name.endsWith('.csv')) {
      setError('Format invalide (CSV attendu)');
      return;
    }

    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete(results) {
        if (results.errors.length > 0) {
          setError(`Erreur de parsing : ${results.errors[0].message}`);
          return;
        }

        if (results.data.length === 0) {
          setError('Le fichier est vide');
          return;
        }

        if (results.data.length > MAX_ROWS) {
          setError(`Trop de lignes (${results.data.length}). Maximum : ${MAX_ROWS}`);
          return;
        }

        const headers = results.meta.fields || [];
        setCsvHeaders(headers);
        setCsvRows(results.data);

        // Auto-mapping : matcher les headers CSV aux champs entite
        const autoMapping: Record<string, string> = {};
        for (const col of columns) {
          const match = headers.find(
            (h) => h.toLowerCase().trim() === col.key.toLowerCase() ||
                   h.toLowerCase().trim() === col.label.toLowerCase(),
          );
          if (match) {
            autoMapping[col.key] = match;
          }
        }
        setMapping(autoMapping);
        setStep('mapping');
      },
    });
  }

  // Etape 2 → 3 : Valider le mapping
  function handleConfirmMapping() {
    const mappedFields = Object.values(mapping).filter(Boolean);
    if (mappedFields.length === 0) {
      setError('Mappez au moins un champ');
      return;
    }
    setError(null);
    setStep('preview');
  }

  // Construire les rows mappees
  function getMappedRows(): Record<string, unknown>[] {
    return csvRows.map((row) => {
      const mapped: Record<string, unknown> = {};
      for (const [field, csvHeader] of Object.entries(mapping)) {
        if (csvHeader && row[csvHeader] !== undefined && row[csvHeader] !== '') {
          mapped[field] = row[csvHeader];
        }
      }
      return mapped;
    });
  }

  // Etape 3 → 4 : Envoyer au backend
  async function handleImport() {
    setLoading(true);
    setError(null);

    try {
      const rows = getMappedRows();
      const importFn = entity === 'contacts' ? importContacts : importCompanies;
      const res: ImportResult = await importFn(rows);
      setResult(res);
      setStep('result');

      if (res.imported > 0) {
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de l\'import');
    } finally {
      setLoading(false);
    }
  }

  // ---------- Rendu par etape ----------

  function renderUpload() {
    return (
      <div className="space-y-4">
        <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center">
          <Upload className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-600 mb-2">
            Glissez un fichier CSV ou cliquez pour sélectionner
          </p>
          <p className="text-xs text-slate-400 mb-4">
            Max {MAX_ROWS} lignes, 5 MB
          </p>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="block mx-auto text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100 cursor-pointer"
          />
        </div>
        {error && (
          <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}
      </div>
    );
  }

  function renderMapping() {
    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Associez les colonnes du CSV aux champs {entity === 'contacts' ? 'du contact' : 'de l\'entreprise'}.
        </p>
        <div className="space-y-3 max-h-[50vh] overflow-y-auto">
          {columns.map((col) => (
            <div key={col.key} className="flex items-center gap-3">
              <span className="text-sm text-slate-700 w-32 flex-shrink-0">{col.label}</span>
              <ArrowRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
              <Select
                options={csvHeaders.map((h) => ({ value: h, label: h }))}
                value={mapping[col.key] || ''}
                onChange={(value) => setMapping((prev) => ({ ...prev, [col.key]: value }))}
                placeholder="Non mappé"
                className="flex-1"
              />
            </div>
          ))}
        </div>
        {error && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</div>
        )}
      </div>
    );
  }

  function renderPreview() {
    const previewRows = getMappedRows().slice(0, 5);
    const mappedKeys = Object.entries(mapping)
      .filter(([, v]) => v)
      .map(([k]) => k);

    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Aperçu des 5 premières lignes ({csvRows.length} lignes au total)
        </p>
        <div className="overflow-x-auto border border-slate-200 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                {mappedKeys.map((key) => {
                  const col = columns.find((c) => c.key === key);
                  return (
                    <th key={key} className="px-3 py-2 text-left text-xs font-medium text-slate-500">
                      {col?.label || key}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {previewRows.map((row, idx) => (
                <tr key={idx}>
                  {mappedKeys.map((key) => (
                    <td key={key} className="px-3 py-2 text-slate-700 whitespace-nowrap">
                      {String(row[key] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {error && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</div>
        )}
      </div>
    );
  }

  function renderResult() {
    if (!result) return null;

    return (
      <div className="space-y-4">
        {/* Resume */}
        <div className={clsx(
          'flex items-center gap-3 px-4 py-3 rounded-lg',
          result.imported > 0 ? 'bg-emerald-50' : 'bg-amber-50',
        )}>
          <CheckCircle className={clsx('w-5 h-5', result.imported > 0 ? 'text-emerald-600' : 'text-amber-600')} />
          <span className="text-sm font-medium text-slate-800">
            {result.imported} {entity === 'contacts' ? 'contact(s)' : 'entreprise(s)'} importé(s)
          </span>
        </div>

        {/* Erreurs */}
        {result.errors.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700">
              {result.errors.length} erreur(s) :
            </p>
            <div className="max-h-[200px] overflow-y-auto border border-red-100 rounded-lg divide-y divide-red-50">
              {result.errors.map((err: ImportRowError, idx: number) => (
                <div key={idx} className="px-4 py-2 text-sm">
                  <span className="font-medium text-red-700">Ligne {err.row}</span>
                  <span className="text-slate-500"> — {err.field} : </span>
                  <span className="text-slate-700">{err.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ---------- Footer ----------

  const STEP_TITLES: Record<Step, string> = {
    upload: 'Charger un fichier CSV',
    mapping: 'Mapper les colonnes',
    preview: 'Aperçu des données',
    result: 'Résultat de l\'import',
  };

  function renderFooter() {
    if (step === 'upload') return null;

    if (step === 'result') {
      return <Button onClick={handleClose}>Fermer</Button>;
    }

    return (
      <>
        <Button
          variant="secondary"
          onClick={() => setStep(step === 'preview' ? 'mapping' : 'upload')}
        >
          Retour
        </Button>
        {step === 'mapping' && (
          <Button onClick={handleConfirmMapping}>Suivant</Button>
        )}
        {step === 'preview' && (
          <Button onClick={handleImport} disabled={loading}>
            {loading ? 'Import en cours...' : `Importer ${csvRows.length} lignes`}
          </Button>
        )}
      </>
    );
  }

  return (
    <Modal open={open} onClose={handleClose} title={STEP_TITLES[step]} size="lg" footer={renderFooter()}>
      {step === 'upload' && renderUpload()}
      {step === 'mapping' && renderMapping()}
      {step === 'preview' && renderPreview()}
      {step === 'result' && renderResult()}
    </Modal>
  );
}
