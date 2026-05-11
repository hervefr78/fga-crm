// =============================================================================
// FGA CRM - Companies Page (liste + CRUD + filtres + import/export)
// =============================================================================

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Building2, Plus, Trash2, Download, Upload,
  FileText, FileSearch, Globe, ChevronUp, ChevronDown, ChevronsUpDown,
} from 'lucide-react';

import { getCompanies, deleteCompany } from '../api/client';
import type { Company } from '../types';
import { COMPANY_SIZE_RANGES } from '../types';
import { Modal, SearchInput, Pagination, LoadingSpinner, EmptyState, ConfirmDialog, Button, FilterBar } from '../components/ui';
import type { FilterDef } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';
import CsvImportModal from '../components/import/CsvImportModal';
import { exportToCsv, COMPANY_CSV_COLUMNS } from '../utils/csv';
import { formatDateFR } from '../utils/format';

// Filtres disponibles
const COMPANY_FILTERS: FilterDef[] = [
  { key: 'size_range', label: 'Taille', type: 'select', options: [...COMPANY_SIZE_RANGES] },
  { key: 'country', label: 'Pays', type: 'select', options: [] },
  {
    key: 'lead_source',
    label: 'Provenance',
    type: 'select',
    options: [
      { value: 'startup_radar', label: 'Startup Radar' },
      { value: 'nomo-ia', label: 'Nomo-IA' },
      { value: 'pleinphare', label: 'Plein Phare Digital' },
    ],
  },
  // Funding multi-source (Phase B 2026-05) — filtres sur les levees detectees par SR
  {
    key: 'funding_series',
    label: 'Serie',
    type: 'select',
    options: [
      { value: 'Pre-seed', label: 'Pre-seed' },
      { value: 'Seed', label: 'Seed' },
      { value: 'Serie A', label: 'Serie A' },
      { value: 'Serie B', label: 'Serie B' },
      { value: 'Serie C', label: 'Serie C+' },
    ],
  },
  {
    key: 'funding_amount_min',
    label: 'Montant min (€)',
    type: 'number',
    placeholder: 'ex: 1000000',
  },
  { key: 'funding_date_after', label: 'Levee apres', type: 'date' },
];

// Colonnes triables côté backend
type SortKey = 'name' | 'industry' | 'size_range' | 'created_at';

const MAX_EXPORT_SIZE = 5000;

export default function CompaniesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sortBy, setSortBy] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [importOpen, setImportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | undefined>(undefined);
  const [deletingCompany, setDeletingCompany] = useState<Company | null>(null);

  // Construire les params avec filtres actifs
  const activeFilters = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== ''),
  );

  const { data, isLoading } = useQuery({
    queryKey: ['companies', { page, search, sortBy, sortDir, ...activeFilters }],
    queryFn: () => getCompanies({
      page, size: 25, search: search || undefined,
      sort_by: sortBy, sort_dir: sortDir,
      ...activeFilters,
    }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCompany(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
      setDeletingCompany(null);
    },
  });

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const handleFilterChange = useCallback((key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }, []);

  const handleFilterReset = useCallback(() => {
    setFilters({});
    setPage(1);
  }, []);

  const handleSort = useCallback((col: SortKey) => {
    if (sortBy === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(col);
      setSortDir('asc');
    }
    setPage(1);
  }, [sortBy]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await getCompanies({
        page: 1, size: MAX_EXPORT_SIZE, search: search || undefined,
        sort_by: sortBy, sort_dir: sortDir,
        ...activeFilters,
      });
      exportToCsv(res.items, 'entreprises.csv', COMPANY_CSV_COLUMNS);
    } catch (err) {
      console.error('[Companies] Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  const openCreate = () => {
    setEditingCompany(undefined);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingCompany(undefined);
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Entreprises</h1>
          <p className="text-slate-400 text-sm mt-1">{data?.total || 0} entreprises</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={handleExport} loading={exporting} size="sm">
            Exporter
          </Button>
          <Button variant="secondary" icon={Upload} onClick={() => setImportOpen(true)} size="sm">
            Importer
          </Button>
          <Button icon={Plus} onClick={openCreate}>
            Nouvelle entreprise
          </Button>
        </div>
      </div>

      {/* Recherche + Filtres */}
      <div className="space-y-3 mb-5">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Rechercher une entreprise..."
        />
        <FilterBar
          filters={COMPANY_FILTERS}
          values={filters}
          onChange={handleFilterChange}
          onReset={handleFilterReset}
        />
      </div>

      {/* Tableau */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.items?.length ? (
          <EmptyState icon={Building2} message="Aucune entreprise trouvée" />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <SortTh col="name" label="Entreprise" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
                  <SortTh col="industry" label="Secteur" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
                  <SortTh col="size_range" label="Taille" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
                  <th className="px-6 py-3 text-center text-xs font-medium text-slate-400 uppercase tracking-wide">Score</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-slate-400 uppercase tracking-wide">Audits</th>
                  <SortTh col="created_at" label="Créé le" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
                  <th className="px-6 py-3 w-12" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((company: Company) => (
                  <tr
                    key={company.id}
                    onClick={() => navigate(`/companies/${company.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-slate-700">{company.name}</p>
                      {company.website && (
                        <p className="text-xs text-slate-400 truncate max-w-xs">{company.website}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{company.industry || '—'}</td>
                    <td className="px-6 py-4 text-sm text-slate-500">{company.size_range || '—'}</td>
                    <td className="px-6 py-4 text-center">
                      {company.audit_score != null ? (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                          company.audit_score >= 50 ? 'bg-green-50 text-green-700' :
                          company.audit_score >= 30 ? 'bg-amber-50 text-amber-700' :
                          'bg-red-50 text-red-700'
                        }`}>
                          {company.audit_score}/75
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-center gap-1.5">
                        <span title="Audit messaging">
                          <FileText className={`w-4 h-4 ${company.has_audit_messaging ? 'text-blue-500' : 'text-slate-200'}`} />
                        </span>
                        <span title="Audit détaillé">
                          <FileSearch className={`w-4 h-4 ${company.has_audit_detailed ? 'text-purple-500' : 'text-slate-200'}`} />
                        </span>
                        <span title="Audit GEO">
                          <Globe className={`w-4 h-4 ${company.has_audit_geo ? 'text-emerald-500' : 'text-slate-200'}`} />
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400 whitespace-nowrap">
                      {formatDateFR(company.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingCompany(company);
                        }}
                        className="p-1 text-slate-300 hover:text-red-500 rounded transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPageChange={setPage}
            />
          </>
        )}
      </div>

      {/* Modal creation / edition */}
      <Modal
        open={formOpen}
        onClose={closeForm}
        title={editingCompany ? "Modifier l'entreprise" : 'Nouvelle entreprise'}
        size="lg"
      >
        <CompanyForm
          company={editingCompany}
          onSuccess={closeForm}
          onCancel={closeForm}
        />
      </Modal>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={!!deletingCompany}
        onClose={() => setDeletingCompany(null)}
        onConfirm={() => deletingCompany && deleteMutation.mutate(deletingCompany.id)}
        title="Supprimer l'entreprise"
        message={`Voulez-vous vraiment supprimer ${deletingCompany?.name} ? Cette action est irréversible.`}
        loading={deleteMutation.isPending}
      />

      {/* Modal import CSV */}
      <CsvImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        entity="companies"
        columns={COMPANY_CSV_COLUMNS}
        onSuccess={() => void queryClient.invalidateQueries({ queryKey: ['companies'] })}
      />
    </div>
  );
}

// -----------------------------------------------------------------------------
// Composant header de colonne triable
// -----------------------------------------------------------------------------

function SortTh({
  col, label, sortBy, sortDir, onSort, align = 'left',
}: {
  col: SortKey;
  label: string;
  sortBy: SortKey;
  sortDir: 'asc' | 'desc';
  onSort: (col: SortKey) => void;
  align?: 'left' | 'center';
}) {
  const active = sortBy === col;
  const Icon = active ? (sortDir === 'asc' ? ChevronUp : ChevronDown) : ChevronsUpDown;
  return (
    <th
      className={`px-6 py-3 text-${align} text-xs font-medium text-slate-400 uppercase tracking-wide cursor-pointer select-none hover:text-slate-600 transition-colors`}
      onClick={() => onSort(col)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <Icon className={`w-3 h-3 ${active ? 'text-primary-500' : 'text-slate-300'}`} />
      </span>
    </th>
  );
}
