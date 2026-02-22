// =============================================================================
// FGA CRM - Page detail d'une entreprise
// =============================================================================

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Globe, Phone, Linkedin, Edit2, Trash2,
  Target, Users, FileSearch, AlertCircle,
} from 'lucide-react';

import {
  getCompany, getContacts, getDeals, getActivities, deleteCompany,
  triggerCompanyAudit,
} from '../api/client';
import type { Company, Contact, Deal, Activity, CompanyAuditResponse } from '../types';
import { Badge, Button, ConfirmDialog, LoadingSpinner, Modal, Tabs } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';
import AuditResultPanel from '../components/audit/AuditResultPanel';

const ACTIVITY_LABELS: Record<string, string> = {
  email: 'Email',
  call: 'Appel',
  meeting: 'Meeting',
  note: 'Note',
  linkedin: 'LinkedIn',
  task: 'Tache',
  audit: 'Audit SR',
};

const STAGE_LABELS: Record<string, string> = {
  new: 'Nouveau',
  contacted: 'Contacte',
  meeting: 'Meeting',
  proposal: 'Proposition',
  negotiation: 'Negociation',
  won: 'Gagne',
  lost: 'Perdu',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau',
  contacted: 'Contacte',
  qualified: 'Qualifie',
  unqualified: 'Non qualifie',
  nurturing: 'Nurturing',
};

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('contacts');
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data: company, isLoading } = useQuery({
    queryKey: ['company', id],
    queryFn: () => getCompany(id!),
    enabled: !!id,
  });

  const { data: contactsData } = useQuery({
    queryKey: ['contacts', { company_id: id }],
    queryFn: () => getContacts({ company_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: dealsData } = useQuery({
    queryKey: ['deals', { company_id: id }],
    queryFn: () => getDeals({ company_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: activitiesData } = useQuery({
    queryKey: ['activities', { company_id: id }],
    queryFn: () => getActivities({ company_id: id, size: 50 }),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCompany(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
      navigate('/companies');
    },
  });

  // Mutation audit avance SR
  const auditMutation = useMutation<CompanyAuditResponse, Error>({
    mutationFn: () => triggerCompanyAudit(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['activities', { company_id: id }] });
      setActiveTab('audit');
    },
  });

  if (isLoading) return <LoadingSpinner />;
  if (!company) {
    return (
      <div className="p-8">
        <p className="text-slate-500">Entreprise non trouvee.</p>
        <Link to="/companies" className="text-primary-600 hover:underline text-sm mt-2 inline-block">
          Retour aux entreprises
        </Link>
      </div>
    );
  }

  const contacts: Contact[] = contactsData?.items || [];
  const deals: Deal[] = dealsData?.items || [];
  const activities: Activity[] = activitiesData?.items || [];

  // Separer audits des autres activites
  const auditActivities = activities.filter((a) => a.type === 'audit');
  const nonAuditActivities = activities.filter((a) => a.type !== 'audit');

  // L'entreprise est-elle eligible a l'audit SR ?
  const canAudit = company.startup_radar_id
    && !company.startup_radar_id.startsWith('inv:');

  const tabs = [
    { key: 'contacts', label: 'Contacts', count: contacts.length },
    { key: 'deals', label: 'Deals', count: deals.length },
    { key: 'activities', label: 'Activites', count: nonAuditActivities.length },
    // Onglet audit conditionnel (si company SR ou si audits existent deja)
    ...(canAudit || auditActivities.length > 0 ? [{
      key: 'audit',
      label: 'Audit SR',
      count: auditActivities.length,
    }] : []),
  ];

  return (
    <div className="p-8">
      {/* Bouton retour */}
      <button
        onClick={() => navigate('/companies')}
        className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Entreprises
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Colonne gauche (2/3) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Carte info */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h1 className="text-xl font-bold text-slate-800 mb-1">{company.name}</h1>
            {company.industry && (
              <p className="text-sm text-slate-500 mb-4">{company.industry}</p>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              {company.website && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Globe className="w-4 h-4 text-slate-400" />
                  <a href={company.website} target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 truncate">
                    {company.domain || company.website}
                  </a>
                </div>
              )}
              {company.phone && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Phone className="w-4 h-4 text-slate-400" />
                  <a href={`tel:${company.phone}`} className="hover:text-primary-600">{company.phone}</a>
                </div>
              )}
              {company.linkedin_url && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Linkedin className="w-4 h-4 text-slate-400" />
                  <a href={company.linkedin_url} target="_blank" rel="noopener noreferrer" className="hover:text-primary-600">
                    LinkedIn
                  </a>
                </div>
              )}
              {company.size_range && (
                <div className="text-slate-500">
                  <span className="text-slate-400">Taille :</span> {company.size_range} employes
                </div>
              )}
              {company.city && (
                <div className="text-slate-500">
                  <span className="text-slate-400">Localisation :</span> {company.city}{company.country ? `, ${company.country}` : ''}
                </div>
              )}
            </div>

            {company.description && (
              <p className="mt-4 text-sm text-slate-600 border-t border-slate-100 pt-4">
                {company.description}
              </p>
            )}
          </div>

          {/* Tabs */}
          <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

          {/* Contenu des tabs */}
          {activeTab !== 'audit' && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
              {activeTab === 'contacts' && (
                contacts.length === 0 ? (
                  <p className="p-6 text-sm text-slate-400 text-center">Aucun contact</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {contacts.map((c) => (
                      <li key={c.id} className="px-6 py-3">
                        <Link
                          to={`/contacts/${c.id}`}
                          className="flex items-center justify-between hover:bg-slate-50 -mx-6 -my-3 px-6 py-3 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <Users className="w-4 h-4 text-slate-400" />
                            <div>
                              <p className="text-sm font-medium text-slate-700">{c.full_name}</p>
                              <p className="text-xs text-slate-400">{c.title || c.email || ''}</p>
                            </div>
                          </div>
                          <Badge variant="default">
                            {STATUS_LABELS[c.status] || c.status}
                          </Badge>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )
              )}

              {activeTab === 'deals' && (
                deals.length === 0 ? (
                  <p className="p-6 text-sm text-slate-400 text-center">Aucun deal</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {deals.map((d) => (
                      <li key={d.id} className="px-6 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Target className="w-4 h-4 text-slate-400" />
                          <div>
                            <p className="text-sm font-medium text-slate-700">{d.title}</p>
                            <p className="text-xs text-slate-400">
                              {STAGE_LABELS[d.stage] || d.stage}
                              {d.amount !== null && ` — ${d.amount.toLocaleString('fr-FR')} ${d.currency}`}
                            </p>
                          </div>
                        </div>
                        <span className="text-xs text-slate-400">
                          {new Date(d.created_at).toLocaleDateString('fr-FR')}
                        </span>
                      </li>
                    ))}
                  </ul>
                )
              )}

              {activeTab === 'activities' && (
                nonAuditActivities.length === 0 ? (
                  <p className="p-6 text-sm text-slate-400 text-center">Aucune activite</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {nonAuditActivities.map((a) => (
                      <li key={a.id} className="px-6 py-3 flex items-center justify-between">
                        <div>
                          <Badge variant="info">{ACTIVITY_LABELS[a.type] || a.type}</Badge>
                          <span className="ml-2 text-sm text-slate-700">{a.subject || '(sans objet)'}</span>
                        </div>
                        <span className="text-xs text-slate-400">
                          {new Date(a.created_at).toLocaleDateString('fr-FR')}
                        </span>
                      </li>
                    ))}
                  </ul>
                )
              )}
            </div>
          )}

          {/* Onglet Audit SR */}
          {activeTab === 'audit' && (
            <div className="space-y-4">
              {/* Bouton lancer audit (dans le contenu de l'onglet) */}
              {canAudit && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-500">
                    {auditActivities.length > 0
                      ? `${auditActivities.length} audit${auditActivities.length > 1 ? 's' : ''} disponible${auditActivities.length > 1 ? 's' : ''}`
                      : 'Aucun audit pour le moment'}
                  </p>
                  <Button
                    icon={FileSearch}
                    variant="secondary"
                    onClick={() => auditMutation.mutate()}
                    disabled={auditMutation.isPending}
                  >
                    {auditMutation.isPending ? 'Chargement...' : 'Lancer un audit'}
                  </Button>
                </div>
              )}

              {/* Resultat mutation */}
              {auditMutation.isSuccess && auditMutation.data && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm text-emerald-700">
                  {auditMutation.data.audits_created > 0 && (
                    <span>{auditMutation.data.audits_created} audit{auditMutation.data.audits_created > 1 ? 's' : ''} cree{auditMutation.data.audits_created > 1 ? 's' : ''}</span>
                  )}
                  {auditMutation.data.audits_skipped > 0 && (
                    <span>{auditMutation.data.audits_created > 0 ? ' — ' : ''}{auditMutation.data.audits_skipped} deja existant{auditMutation.data.audits_skipped > 1 ? 's' : ''}</span>
                  )}
                  {auditMutation.data.audits_created === 0 && auditMutation.data.audits_skipped === 0 && (
                    <span>Aucun audit disponible pour cette entreprise</span>
                  )}
                </div>
              )}

              {/* Erreurs mutation */}
              {auditMutation.isError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{auditMutation.error?.message || 'Erreur lors du lancement de l\'audit'}</span>
                </div>
              )}

              {/* Erreurs SR */}
              {auditMutation.data?.errors && auditMutation.data.errors.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
                  <p className="font-medium mb-1">Avertissements :</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {auditMutation.data.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Liste des audits */}
              {auditActivities.length > 0 ? (
                <div className="space-y-4">
                  {auditActivities.map((a) => (
                    a.metadata_ ? (
                      <AuditResultPanel
                        key={a.id}
                        metadata={a.metadata_}
                        subject={a.subject || 'Audit'}
                        createdAt={a.created_at}
                      />
                    ) : (
                      <div key={a.id} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                        <p className="text-sm text-slate-700">{a.subject || 'Audit'}</p>
                        {a.content && <p className="text-sm text-slate-500 mt-1">{a.content}</p>}
                        <p className="text-xs text-slate-400 mt-2">
                          {new Date(a.created_at).toLocaleDateString('fr-FR')}
                        </p>
                      </div>
                    )
                  ))}
                </div>
              ) : (
                !canAudit && (
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center text-slate-400">
                    <FileSearch className="w-8 h-8 mx-auto mb-2" />
                    <p className="text-sm">Aucun audit disponible</p>
                  </div>
                )
              )}
            </div>
          )}
        </div>

        {/* Colonne droite (1/3) */}
        <div className="space-y-4">
          {/* Actions */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-2">
            <Button icon={Edit2} variant="secondary" className="w-full" onClick={() => setEditOpen(true)}>
              Modifier
            </Button>
            <Button icon={Trash2} variant="danger" className="w-full" onClick={() => setDeleteOpen(true)}>
              Supprimer
            </Button>
            {canAudit && (
              <Button
                icon={FileSearch}
                variant="secondary"
                className="w-full"
                onClick={() => {
                  auditMutation.mutate();
                }}
                disabled={auditMutation.isPending}
              >
                {auditMutation.isPending ? 'Chargement...' : 'Audit avance'}
              </Button>
            )}
          </div>

          {/* Metadata */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-sm text-slate-500 space-y-1">
            <p><span className="text-slate-400">Creee le :</span> {new Date(company.created_at).toLocaleDateString('fr-FR')}</p>
            {company.domain && (
              <p><span className="text-slate-400">Domaine :</span> {company.domain}</p>
            )}
            {company.startup_radar_id && (
              <p><span className="text-slate-400">Startup Radar :</span> {company.startup_radar_id}</p>
            )}
          </div>
        </div>
      </div>

      {/* Modal edition */}
      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Modifier l'entreprise"
        size="lg"
      >
        <CompanyForm
          company={company as Company}
          onSuccess={() => {
            setEditOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['company', id] });
          }}
          onCancel={() => setEditOpen(false)}
        />
      </Modal>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
        title="Supprimer l'entreprise"
        message={`Voulez-vous vraiment supprimer ${company.name} ? Cette action est irreversible.`}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
