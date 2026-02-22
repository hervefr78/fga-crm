// =============================================================================
// FGA CRM - Companies Page (liste + CRUD)
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Building2, Plus, Trash2 } from 'lucide-react';

import { getCompanies, deleteCompany } from '../api/client';
import type { Company } from '../types';
import { Modal, SearchInput, Pagination, LoadingSpinner, EmptyState, ConfirmDialog, Button } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | undefined>(undefined);
  const [deletingCompany, setDeletingCompany] = useState<Company | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['companies', { page, search }],
    queryFn: () => getCompanies({ page, size: 25, search: search || undefined }),
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

  const openCreate = () => {
    setEditingCompany(undefined);
    setFormOpen(true);
  };

  const openEdit = (company: Company) => {
    setEditingCompany(company);
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
        <Button icon={Plus} onClick={openCreate}>
          Nouvelle entreprise
        </Button>
      </div>

      {/* Recherche */}
      <div className="mb-5">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Rechercher une entreprise..."
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
                    onClick={() => openEdit(company)}
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
    </div>
  );
}
