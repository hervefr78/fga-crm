// =============================================================================
// FGA CRM - Companies Page (liste + CRUD + filtres + import/export)
// =============================================================================

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Building2, Plus, Trash2, Download, Upload } from 'lucide-react';

import { getCompanies, deleteCompany } from '../api/client';
import type { Company } from '../types';
import { COMPANY_SIZE_RANGES } from '../types';
import { Modal, SearchInput, Pagination, LoadingSpinner, EmptyState, ConfirmDialog, Button, FilterBar } from '../components/ui';
import type { FilterDef } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';
import CsvImportModal from '../components/import/CsvImportModal';
import { exportToCsv, COMPANY_CSV_COLUMNS } from '../utils/csv';

// Filtres disponibles
const COMPANY_FILTERS: FilterDef[] = [
  { key: 'size_range', label: 'Taille', type: 'select', options: [...COMPANY_SIZE_RANGES] },
  { key: 'country', label: 'Pays', type: 'select', options: [] }, // Texte libre via select vide → on utilisera un input
];

const MAX_EXPORT_SIZE = 5000;

export default function CompaniesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Record<string, string>>({});
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
    queryKey: ['companies', { page, search, ...activeFilters }],
    queryFn: () => getCompanies({ page, size: 25, search: search || undefined, ...activeFilters }),
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

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await getCompanies({ page: 1, size: MAX_EXPORT_SIZE, search: search || undefined, ...activeFilters });
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
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Entreprise</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Secteur</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Taille</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Domaine</th>
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
                    <td className="px-6 py-4 text-sm text-slate-500">{company.domain || '—'}</td>
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
