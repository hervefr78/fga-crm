// =============================================================================
// FGA CRM - Utilitaires CSV (export via papaparse)
// =============================================================================

import Papa from 'papaparse';

// ---------- Types ----------

export interface CsvColumn {
  key: string;
  label: string;
}

// ---------- Colonnes par entite ----------

export const CONTACT_CSV_COLUMNS: CsvColumn[] = [
  { key: 'first_name', label: 'Prénom' },
  { key: 'last_name', label: 'Nom' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Téléphone' },
  { key: 'title', label: 'Poste' },
  { key: 'job_level', label: 'Niveau' },
  { key: 'department', label: 'Département' },
  { key: 'status', label: 'Statut' },
  { key: 'source', label: 'Source' },
  { key: 'is_decision_maker', label: 'Décideur' },
  { key: 'linkedin_url', label: 'LinkedIn' },
  { key: 'lead_score', label: 'Score' },
  { key: 'created_at', label: 'Créé le' },
];

export const COMPANY_CSV_COLUMNS: CsvColumn[] = [
  { key: 'name', label: 'Nom' },
  { key: 'domain', label: 'Domaine' },
  { key: 'website', label: 'Site web' },
  { key: 'industry', label: 'Secteur' },
  { key: 'size_range', label: 'Taille' },
  { key: 'country', label: 'Pays' },
  { key: 'city', label: 'Ville' },
  { key: 'phone', label: 'Téléphone' },
  { key: 'linkedin_url', label: 'LinkedIn' },
  { key: 'created_at', label: 'Créé le' },
];

// ---------- Export CSV ----------

const MAX_EXPORT_ROWS = 5000;

/**
 * Genere et telecharge un fichier CSV a partir des donnees fournies.
 * Limite a MAX_EXPORT_ROWS lignes (DC1).
 */
export function exportToCsv<T extends Record<string, unknown>>(
  data: T[],
  filename: string,
  columns: CsvColumn[],
): void {
  const rows = data.slice(0, MAX_EXPORT_ROWS);

  // Construire les lignes avec les labels comme headers
  const csvData = rows.map((item) => {
    const row: Record<string, unknown> = {};
    for (const col of columns) {
      row[col.label] = item[col.key] ?? '';
    }
    return row;
  });

  const csv = Papa.unparse(csvData, { header: true });

  // Telecharger le fichier
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
