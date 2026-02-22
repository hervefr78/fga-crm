// =============================================================================
// FGA CRM - Page Email (envoyes + templates)
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Mail, Plus, Trash2, Edit2, FileText } from 'lucide-react';

import {
  getEmails,
  getEmailTemplates,
  deleteEmailTemplate,
} from '../api/client';
import {
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  LoadingSpinner,
  Modal,
  Pagination,
  SearchInput,
  Tabs,
} from '../components/ui';
import ComposeModal from '../components/email/ComposeModal';
import TemplateForm from '../components/email/TemplateForm';
import type { EmailTemplate, PaginatedResponse, SentEmail } from '../types';

// ---------- Composant ----------

export default function EmailPage() {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('sent');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');

  // Modales
  const [composeOpen, setComposeOpen] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | undefined>();
  const [deleteTemplateId, setDeleteTemplateId] = useState<string | null>(null);
  const [deleteTemplateName, setDeleteTemplateName] = useState('');

  // ---------- Queries ----------

  const { data: emailsData, isLoading: emailsLoading } = useQuery<PaginatedResponse<SentEmail>>({
    queryKey: ['emails', page, search],
    queryFn: () => getEmails({ page, size: 25, ...(search ? { search } : {}) }),
    enabled: activeTab === 'sent',
  });

  const { data: templatesData, isLoading: templatesLoading } = useQuery<PaginatedResponse<EmailTemplate>>({
    queryKey: ['email-templates', page, search],
    queryFn: () => getEmailTemplates({ page, size: 25, ...(search ? { search } : {}) }),
    enabled: activeTab === 'templates',
  });

  // ---------- Delete template ----------

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteEmailTemplate(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['email-templates'] });
      setDeleteTemplateId(null);
    },
  });

  // Reset page/search quand on change de tab
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    setPage(1);
    setSearch('');
  };

  // ---------- Rendu ----------

  const tabs = [
    { key: 'sent', label: 'Envoyes', count: emailsData?.total },
    { key: 'templates', label: 'Templates', count: templatesData?.total },
  ];

  return (
    <div className="p-8">
      {/* En-tete */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-50 rounded-lg flex items-center justify-center">
            <Mail className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Email</h1>
            <p className="text-sm text-slate-400">Envoyer et gerer vos emails</p>
          </div>
        </div>
        <div className="flex gap-2">
          {activeTab === 'templates' && (
            <Button
              icon={Plus}
              variant="secondary"
              onClick={() => {
                setEditingTemplate(undefined);
                setTemplateModalOpen(true);
              }}
            >
              Nouveau template
            </Button>
          )}
          <Button icon={Plus} onClick={() => setComposeOpen(true)}>
            Nouveau message
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={handleTabChange} />

      {/* Recherche */}
      <div className="mt-4 mb-4 w-80">
        <SearchInput
          value={search}
          onChange={(v: string) => {
            setSearch(v);
            setPage(1);
          }}
          placeholder={activeTab === 'sent' ? 'Rechercher par objet...' : 'Rechercher par nom...'}
        />
      </div>

      {/* Tab Envoyes */}
      {activeTab === 'sent' && (
        emailsLoading ? (
          <LoadingSpinner />
        ) : !emailsData || emailsData.items.length === 0 ? (
          <EmptyState
            icon={Mail}
            message="Aucun email envoye."
            action={
              <Button size="sm" onClick={() => setComposeOpen(true)}>
                Envoyer un email
              </Button>
            }
          />
        ) : (
          <>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Objet
                    </th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Destinataire
                    </th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Template
                    </th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {emailsData.items.map((email) => (
                    <tr key={email.id} className="hover:bg-slate-25 transition-colors">
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-slate-700 truncate max-w-xs">
                          {email.subject || '(sans objet)'}
                        </p>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-500">
                        {email.to_email}
                      </td>
                      <td className="px-6 py-4">
                        {email.template_name ? (
                          <Badge variant="info">{email.template_name}</Badge>
                        ) : (
                          <span className="text-xs text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-500">
                        {new Date(email.created_at).toLocaleDateString('fr-FR', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {emailsData.pages > 1 && (
              <div className="mt-4">
                <Pagination
                  page={page}
                  pages={emailsData.pages}
                  total={emailsData.total}
                  onPageChange={setPage}
                />
              </div>
            )}
          </>
        )
      )}

      {/* Tab Templates */}
      {activeTab === 'templates' && (
        templatesLoading ? (
          <LoadingSpinner />
        ) : !templatesData || templatesData.items.length === 0 ? (
          <EmptyState
            icon={FileText}
            message="Aucun template."
            action={
              <Button
                size="sm"
                onClick={() => {
                  setEditingTemplate(undefined);
                  setTemplateModalOpen(true);
                }}
              >
                Creer un template
              </Button>
            }
          />
        ) : (
          <>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Nom
                    </th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Objet
                    </th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Variables
                    </th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Date
                    </th>
                    <th className="text-right text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {templatesData.items.map((tmpl) => (
                    <tr key={tmpl.id} className="hover:bg-slate-25 transition-colors">
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-slate-700">{tmpl.name}</p>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-500 truncate max-w-xs">
                        {tmpl.subject}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {(tmpl.variables || []).map((v) => (
                            <span
                              key={v}
                              className="px-1.5 py-0.5 text-xs bg-slate-100 text-slate-500 rounded"
                            >
                              {`{{${v}}}`}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-500">
                        {new Date(tmpl.created_at).toLocaleDateString('fr-FR')}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => {
                              setEditingTemplate(tmpl);
                              setTemplateModalOpen(true);
                            }}
                            className="p-1.5 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                            title="Modifier"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => {
                              setDeleteTemplateId(tmpl.id);
                              setDeleteTemplateName(tmpl.name);
                            }}
                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {templatesData.pages > 1 && (
              <div className="mt-4">
                <Pagination
                  page={page}
                  pages={templatesData.pages}
                  total={templatesData.total}
                  onPageChange={setPage}
                />
              </div>
            )}
          </>
        )
      )}

      {/* Modal compose */}
      <ComposeModal
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
      />

      {/* Modal template */}
      <Modal
        open={templateModalOpen}
        onClose={() => setTemplateModalOpen(false)}
        title={editingTemplate ? 'Modifier le template' : 'Nouveau template'}
        size="lg"
      >
        <TemplateForm
          template={editingTemplate}
          onSuccess={() => setTemplateModalOpen(false)}
          onCancel={() => setTemplateModalOpen(false)}
        />
      </Modal>

      {/* Dialog suppression template */}
      <ConfirmDialog
        open={deleteTemplateId !== null}
        onClose={() => setDeleteTemplateId(null)}
        onConfirm={() => deleteTemplateId && deleteMutation.mutate(deleteTemplateId)}
        title="Supprimer le template"
        message={`Voulez-vous vraiment supprimer le template "${deleteTemplateName}" ? Cette action est irreversible.`}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
