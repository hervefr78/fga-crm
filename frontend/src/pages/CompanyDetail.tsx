// =============================================================================
// FGA CRM - Page detail d'une entreprise
// =============================================================================

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Globe, Phone, Linkedin, Edit2, Trash2,
  Target, Users,
} from 'lucide-react';

import {
  getCompany, getContacts, getDeals, getActivities, deleteCompany,
} from '../api/client';
import type { Company, Contact, Deal, Activity } from '../types';
import { Badge, Button, ConfirmDialog, LoadingSpinner, Modal, Tabs } from '../components/ui';
import CompanyForm from '../components/companies/CompanyForm';

const ACTIVITY_LABELS: Record<string, string> = {
  email: 'Email',
  call: 'Appel',
  meeting: 'Meeting',
  note: 'Note',
  linkedin: 'LinkedIn',
  task: 'Tache',
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

  const tabs = [
    { key: 'contacts', label: 'Contacts', count: contacts.length },
    { key: 'deals', label: 'Deals', count: deals.length },
    { key: 'activities', label: 'Activites', count: activities.length },
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
              activities.length === 0 ? (
                <p className="p-6 text-sm text-slate-400 text-center">Aucune activite</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {activities.map((a) => (
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
          </div>

          {/* Metadata */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-sm text-slate-500 space-y-1">
            <p><span className="text-slate-400">Creee le :</span> {new Date(company.created_at).toLocaleDateString('fr-FR')}</p>
            {company.domain && (
              <p><span className="text-slate-400">Domaine :</span> {company.domain}</p>
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
