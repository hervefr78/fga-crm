// =============================================================================
// FGA CRM - Contacts Page (liste + CRUD)
// =============================================================================

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, Plus, Trash2, Download, Upload } from 'lucide-react';

import { getContacts, deleteContact } from '../api/client';
import type { Contact } from '../types';
import { CONTACT_SOURCES, CONTACT_STATUSES } from '../types';
import { Modal, SearchInput, Pagination, LoadingSpinner, EmptyState, ConfirmDialog, Badge, Button, FilterBar } from '../components/ui';
import type { FilterDef } from '../components/ui';
import ContactForm from '../components/contacts/ContactForm';
import CsvImportModal from '../components/import/CsvImportModal';
import { exportToCsv, CONTACT_CSV_COLUMNS } from '../utils/csv';

const STATUS_COLORS: Record<string, 'default' | 'info' | 'success' | 'danger' | 'warning'> = {
  new: 'default',
  contacted: 'info',
  qualified: 'success',
  unqualified: 'danger',
  nurturing: 'warning',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau',
  contacted: 'Contacté',
  qualified: 'Qualifié',
  unqualified: 'Non qualifié',
  nurturing: 'Nurturing',
};

// Filtres disponibles
const CONTACT_FILTERS: FilterDef[] = [
  { key: 'source', label: 'Source', type: 'select', options: [...CONTACT_SOURCES] },
  { key: 'status', label: 'Statut', type: 'select', options: [...CONTACT_STATUSES] },
  { key: 'is_decision_maker', label: 'Décideur', type: 'boolean' },
  { key: 'has_email', label: 'Email', type: 'boolean' },
  { key: 'created_after', label: 'Créé après', type: 'date' },
  { key: 'created_before', label: 'Créé avant', type: 'date' },
];

const MAX_EXPORT_SIZE = 5000;

export default function ContactsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [importOpen, setImportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<Contact | undefined>(undefined);
  const [deletingContact, setDeletingContact] = useState<Contact | null>(null);

  // Construire les params de requete avec filtres actifs
  const activeFilters = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== ''),
  );

  const { data, isLoading } = useQuery({
    queryKey: ['contacts', { page, search, ...activeFilters }],
    queryFn: () => getContacts({ page, size: 25, search: search || undefined, ...activeFilters }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteContact(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contacts'] });
      setDeletingContact(null);
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
      const res = await getContacts({ page: 1, size: MAX_EXPORT_SIZE, search: search || undefined, ...activeFilters });
      exportToCsv(res.items, 'contacts.csv', CONTACT_CSV_COLUMNS);
    } catch (err) {
      console.error('[Contacts] Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  const openCreate = () => {
    setEditingContact(undefined);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingContact(undefined);
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Contacts</h1>
          <p className="text-slate-400 text-sm mt-1">{data?.total || 0} contacts au total</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={handleExport} loading={exporting} size="sm">
            Exporter
          </Button>
          <Button variant="secondary" icon={Upload} onClick={() => setImportOpen(true)} size="sm">
            Importer
          </Button>
          <Button icon={Plus} onClick={openCreate}>
            Nouveau contact
          </Button>
        </div>
      </div>

      {/* Recherche + Filtres */}
      <div className="space-y-3 mb-5">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Rechercher un contact..."
        />
        <FilterBar
          filters={CONTACT_FILTERS}
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
          <EmptyState icon={Users} message="Aucun contact trouvé" />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Nom</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Titre</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Statut</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Score</th>
                  <th className="px-6 py-3 w-12" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((contact: Contact) => (
                  <tr
                    key={contact.id}
                    onClick={() => navigate(`/contacts/${contact.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-slate-700">{contact.full_name}</p>
                      {contact.job_level && (
                        <p className="text-xs text-slate-400">{contact.job_level}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{contact.title || '—'}</td>
                    <td className="px-6 py-4 text-sm text-slate-500">{contact.email || '—'}</td>
                    <td className="px-6 py-4">
                      <Badge variant={STATUS_COLORS[contact.status] || 'default'}>
                        {STATUS_LABELS[contact.status] || contact.status}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{contact.lead_score}</td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingContact(contact);
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
        title={editingContact ? 'Modifier le contact' : 'Nouveau contact'}
        size="lg"
      >
        <ContactForm
          contact={editingContact}
          onSuccess={closeForm}
          onCancel={closeForm}
        />
      </Modal>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={!!deletingContact}
        onClose={() => setDeletingContact(null)}
        onConfirm={() => deletingContact && deleteMutation.mutate(deletingContact.id)}
        title="Supprimer le contact"
        message={`Voulez-vous vraiment supprimer ${deletingContact?.full_name} ? Cette action est irréversible.`}
        loading={deleteMutation.isPending}
      />

      {/* Modal import CSV */}
      <CsvImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        entity="contacts"
        columns={CONTACT_CSV_COLUMNS}
        onSuccess={() => void queryClient.invalidateQueries({ queryKey: ['contacts'] })}
      />
    </div>
  );
}
