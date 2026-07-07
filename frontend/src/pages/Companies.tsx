// =============================================================================
// FGA CRM - Companies Page (liste + CRUD + filtres + import/export)
// =============================================================================

import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Building2, Plus, Trash2, Download, Upload,
  FileText, FileSearch, Globe, ChevronUp, ChevronDown, ChevronsUpDown,
} from 'lucide-react';

import { getCompanies, deleteCompany } from '../api/client';
import type { Company } from '../types';
import { COMPANY_SIZE_RANGES, isManagerOrAbove } from '../types';
import { useAuth } from '../contexts/useAuth';
import { Modal, SearchInput, Pagination, LoadingSpinner, EmptyState, ConfirmDialog, Button, FilterBar } from '../components/ui';
import type { FilterDef } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';
import CompanyBulkActionBar from '../components/companies/CompanyBulkActionBar';
import { useCompanyBulkAction, isAuditEligible } from '../components/companies/useCompanyBulkAction';
import {
  CompanySortKey, parseListParams, buildListParams, saveCompaniesListQuery,
} from '../components/companies/companiesListState';
import CsvImportModal from '../components/import/CsvImportModal';
import { exportToCsv, COMPANY_CSV_COLUMNS } from '../utils/csv';
import { formatDateFR, formatAmountMillions } from '../utils/format';

// Filtres disponibles
const COMPANY_FILTERS: FilterDef[] = [
  { key: 'size_range', label: 'Taille', type: 'select', options: [...COMPANY_SIZE_RANGES] },
  {
    key: 'industry',
    label: 'Secteur',
    type: 'select',
    options: [
      { value: 'Intelligence Artificielle', label: 'IA' },
      { value: 'Santé, MedTech', label: 'Santé / MedTech' },
      { value: 'Biotech', label: 'Biotech' },
      { value: 'Finance, FinTech', label: 'FinTech' },
      { value: 'Deep Tech', label: 'Deep Tech' },
      { value: 'Energie', label: 'Énergie' },
      { value: 'Software', label: 'Software' },
      { value: 'Mobilité', label: 'Mobilité' },
      { value: 'Education, EdTech', label: 'EdTech' },
      { value: 'Recrutement, RH', label: 'RH' },
      { value: 'Environnement', label: 'Environnement' },
      { value: 'Industriel', label: 'Industriel' },
    ],
  },
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

// Colonnes triables côté backend (source unique : companiesListState — DC8)
type SortKey = CompanySortKey;

// Cles de filtres presentes dans l'URL
const FILTER_KEYS = COMPANY_FILTERS.map((f) => f.key);

const MAX_EXPORT_SIZE = 5000;

export default function CompaniesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Etat de vue (recherche, page, tri, filtres) porte par l'URL : le retour
  // depuis une fiche (back navigateur / liens du detail) restaure la liste
  // filtree telle quelle. `replace: true` : pas d'entree d'historique par frappe.
  const [searchParams, setSearchParams] = useSearchParams();
  const view = parseListParams(searchParams, FILTER_KEYS);
  const { search, page, sortBy, sortDir, filters } = view;

  const updateView = useCallback((patch: Partial<typeof view>) => {
    setSearchParams(
      (prev) => buildListParams({ ...parseListParams(prev, FILTER_KEYS), ...patch }, FILTER_KEYS),
      { replace: true },
    );
  }, [setSearchParams]);

  // Memorise le dernier etat de vue pour les liens "Entreprises" du detail.
  const viewQuery = searchParams.toString();
  useEffect(() => {
    saveCompaniesListQuery(viewQuery);
  }, [viewQuery]);

  const [importOpen, setImportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | undefined>(undefined);
  const [deletingCompany, setDeletingCompany] = useState<Company | null>(null);

  // Selection multiple + actions groupees (audit / recherche de contacts)
  const { user } = useAuth();
  const canAudit = isManagerOrAbove(user); // audit SR reserve managers/admins
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmAction, setConfirmAction] = useState<'audit' | 'contacts' | null>(null);
  const bulk = useCompanyBulkAction();

  // Construire les params avec filtres actifs
  const activeFilters = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== ''),
  );

  // Reset la selection quand la vue change (page / tri / recherche / filtres).
  useEffect(() => {
    setSelectedIds(new Set());
  }, [viewQuery]);

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
    updateView({ search: value, page: 1 });
  };

  const handleFilterChange = useCallback((key: string, value: string) => {
    updateView({ filters: { ...filters, [key]: value }, page: 1 });
  }, [updateView, filters]);

  const handleFilterReset = useCallback(() => {
    updateView({ filters: {}, page: 1 });
  }, [updateView]);

  const handleSort = useCallback((col: SortKey) => {
    if (sortBy === col) {
      updateView({ sortDir: sortDir === 'asc' ? 'desc' : 'asc', page: 1 });
    } else {
      updateView({ sortBy: col, sortDir: 'asc', page: 1 });
    }
  }, [updateView, sortBy, sortDir]);

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

  // --- Selection multiple (sur la page courante) ---
  const items: Company[] = data?.items ?? [];
  const allSelected = items.length > 0 && items.every((c) => selectedIds.has(c.id));
  const someSelected = items.some((c) => selectedIds.has(c.id));
  const selectedCompanies = items.filter((c) => selectedIds.has(c.id));
  const eligibleAuditCount = selectedCompanies.filter(isAuditEligible).length;
  const skippedAuditCount = selectedCompanies.length - eligibleAuditCount;

  const toggleOne = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (items.every((c) => prev.has(c.id))) {
        items.forEach((c) => next.delete(c.id));
      } else {
        items.forEach((c) => next.add(c.id));
      }
      return next;
    });
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

      {/* Barre d'actions groupees (selection multiple) */}
      {(selectedIds.size > 0 || bulk.action) && (
        <div className="mb-4">
          <CompanyBulkActionBar
            selectedCount={selectedCompanies.length}
            canAudit={canAudit}
            onAudit={() => setConfirmAction('audit')}
            onContacts={() => setConfirmAction('contacts')}
            onClear={() => setSelectedIds(new Set())}
            bulk={bulk}
          />
        </div>
      )}

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
                  <th className="px-4 py-3 w-10">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      ref={(el) => { if (el) el.indeterminate = !allSelected && someSelected; }}
                      onChange={toggleAll}
                      aria-label="Tout selectionner"
                      className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
                    />
                  </th>
                  <SortTh col="name" label="Entreprise" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
                  <SortTh col="industry" label="Secteur" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
                  <SortTh col="size_range" label="Taille" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
                  <SortTh col="funding_amount" label="Levée" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} align="left" />
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
                    <td className="px-4 py-4" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(company.id)}
                        onChange={() => toggleOne(company.id)}
                        aria-label={`Selectionner ${company.name}`}
                        className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-slate-700">{company.name}</p>
                      {company.website && (
                        <p className="text-xs text-slate-400 truncate max-w-xs">{company.website}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{company.industry || '—'}</td>
                    <td className="px-6 py-4 text-sm text-slate-500">{company.size_range || '—'}</td>
                    <td className="px-6 py-4">
                      {company.funding_amount != null ? (
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-medium text-emerald-700">
                            {formatAmountMillions(company.funding_amount)}
                          </span>
                          {company.funding_series && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 whitespace-nowrap">
                              {company.funding_series}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
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
              onPageChange={(p) => updateView({ page: p })}
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

      {/* Confirmation des actions groupees (operations couteuses) */}
      <ConfirmDialog
        open={confirmAction !== null}
        onClose={() => setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction === 'audit') bulk.startAudit(selectedCompanies);
          else if (confirmAction === 'contacts') bulk.startContacts(selectedCompanies);
          setConfirmAction(null);
        }}
        title={confirmAction === 'audit' ? "Lancer l'audit ?" : 'Chercher les contacts ?'}
        message={
          confirmAction === 'audit'
            ? `${eligibleAuditCount} audit(s) SR vont etre lances${
                skippedAuditCount > 0
                  ? ` (${skippedAuditCount} sans lien Startup Radar seront ignorees)`
                  : ''
              }. Operation longue (plusieurs minutes par entreprise).`
            : `${selectedCompanies.length} recherche(s) de contacts (Icypeas) vont etre lancees. Consomme des credits d'enrichissement.`
        }
        confirmLabel="Lancer"
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
