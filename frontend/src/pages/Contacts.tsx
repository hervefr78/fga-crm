// =============================================================================
// FGA CRM - Contacts Page (liste + CRUD)
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, Plus, Trash2 } from 'lucide-react';

import { getContacts, deleteContact } from '../api/client';
import type { Contact } from '../types';
import { Modal, SearchInput, Pagination, LoadingSpinner, EmptyState, ConfirmDialog, Badge, Button } from '../components/ui';
import ContactForm from '../components/contacts/ContactForm';

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

export default function ContactsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<Contact | undefined>(undefined);
  const [deletingContact, setDeletingContact] = useState<Contact | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['contacts', { page, search }],
    queryFn: () => getContacts({ page, size: 25, search: search || undefined }),
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

  const openCreate = () => {
    setEditingContact(undefined);
    setFormOpen(true);
  };

  const openEdit = (contact: Contact) => {
    setEditingContact(contact);
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
        <Button icon={Plus} onClick={openCreate}>
          Nouveau contact
        </Button>
      </div>

      {/* Recherche */}
      <div className="mb-5">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Rechercher un contact..."
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
                    onClick={() => openEdit(contact)}
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
    </div>
  );
}
