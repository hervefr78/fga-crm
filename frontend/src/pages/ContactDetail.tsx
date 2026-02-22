// =============================================================================
// FGA CRM - Page detail d'un contact
// =============================================================================

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Mail, Phone, Linkedin, Edit2, Trash2,
  Calendar, Target, CheckCircle2,
} from 'lucide-react';

import {
  getContact, getActivities, getDeals, getTasks, deleteContact,
} from '../api/client';
import type { Contact, Activity, Deal, Task } from '../types';
import { Badge, Button, ConfirmDialog, LoadingSpinner, Modal, Tabs } from '../components/ui';
import ContactForm from '../components/contacts/ContactForm';
import ComposeModal from '../components/email/ComposeModal';

const STATUS_COLORS: Record<string, 'default' | 'info' | 'success' | 'danger' | 'warning'> = {
  new: 'default',
  contacted: 'info',
  qualified: 'success',
  unqualified: 'danger',
  nurturing: 'warning',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau',
  contacted: 'Contacte',
  qualified: 'Qualifie',
  unqualified: 'Non qualifie',
  nurturing: 'Nurturing',
};

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

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('activities');
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [composeOpen, setComposeOpen] = useState(false);

  const { data: contact, isLoading } = useQuery({
    queryKey: ['contact', id],
    queryFn: () => getContact(id!),
    enabled: !!id,
  });

  const { data: activitiesData } = useQuery({
    queryKey: ['activities', { contact_id: id }],
    queryFn: () => getActivities({ contact_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: dealsData } = useQuery({
    queryKey: ['deals', { contact_id: id }],
    queryFn: () => getDeals({ contact_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: tasksData } = useQuery({
    queryKey: ['tasks', { contact_id: id }],
    queryFn: () => getTasks({ contact_id: id, size: 50 }),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteContact(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contacts'] });
      navigate('/contacts');
    },
  });

  if (isLoading) return <LoadingSpinner />;
  if (!contact) {
    return (
      <div className="p-8">
        <p className="text-slate-500">Contact non trouve.</p>
        <Link to="/contacts" className="text-primary-600 hover:underline text-sm mt-2 inline-block">
          Retour aux contacts
        </Link>
      </div>
    );
  }

  const activities: Activity[] = activitiesData?.items || [];
  const deals: Deal[] = dealsData?.items || [];
  const tasks: Task[] = tasksData?.items || [];

  const tabs = [
    { key: 'activities', label: 'Activites', count: activities.length },
    { key: 'deals', label: 'Deals', count: deals.length },
    { key: 'tasks', label: 'Taches', count: tasks.length },
  ];

  return (
    <div className="p-8">
      {/* Bouton retour */}
      <button
        onClick={() => navigate('/contacts')}
        className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Contacts
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Colonne gauche (2/3) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Carte info */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h1 className="text-xl font-bold text-slate-800">{contact.full_name}</h1>
                {contact.title && (
                  <p className="text-sm text-slate-500 mt-0.5">{contact.title}</p>
                )}
              </div>
              <Badge variant={STATUS_COLORS[contact.status] || 'default'}>
                {STATUS_LABELS[contact.status] || contact.status}
              </Badge>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              {contact.email && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Mail className="w-4 h-4 text-slate-400" />
                  <a href={`mailto:${contact.email}`} className="hover:text-primary-600">{contact.email}</a>
                </div>
              )}
              {contact.phone && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Phone className="w-4 h-4 text-slate-400" />
                  <a href={`tel:${contact.phone}`} className="hover:text-primary-600">{contact.phone}</a>
                </div>
              )}
              {contact.linkedin_url && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Linkedin className="w-4 h-4 text-slate-400" />
                  <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="hover:text-primary-600 truncate">
                    LinkedIn
                  </a>
                </div>
              )}
              {contact.source && (
                <div className="text-slate-500">
                  <span className="text-slate-400">Source :</span> {contact.source}
                </div>
              )}
              <div className="text-slate-500">
                <span className="text-slate-400">Score :</span> {contact.lead_score}/100
              </div>
              {contact.job_level && (
                <div className="text-slate-500">
                  <span className="text-slate-400">Niveau :</span> {contact.job_level}
                </div>
              )}
            </div>
          </div>

          {/* Tabs */}
          <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

          {/* Contenu des tabs */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
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

            {activeTab === 'tasks' && (
              tasks.length === 0 ? (
                <p className="p-6 text-sm text-slate-400 text-center">Aucune tache</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {tasks.map((t) => (
                    <li key={t.id} className="px-6 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className={`w-4 h-4 ${t.is_completed ? 'text-emerald-500' : 'text-slate-300'}`} />
                        <div>
                          <p className={`text-sm ${t.is_completed ? 'text-slate-400 line-through' : 'text-slate-700'}`}>
                            {t.title}
                          </p>
                          {t.due_date && (
                            <p className="text-xs text-slate-400 flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {new Date(t.due_date).toLocaleDateString('fr-FR')}
                            </p>
                          )}
                        </div>
                      </div>
                      <Badge variant={t.is_completed ? 'success' : 'default'}>
                        {t.is_completed ? 'Fait' : t.priority}
                      </Badge>
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
            {contact.email && (
              <Button icon={Mail} variant="primary" className="w-full" onClick={() => setComposeOpen(true)}>
                Envoyer un email
              </Button>
            )}
            <Button icon={Edit2} variant="secondary" className="w-full" onClick={() => setEditOpen(true)}>
              Modifier
            </Button>
            <Button icon={Trash2} variant="danger" className="w-full" onClick={() => setDeleteOpen(true)}>
              Supprimer
            </Button>
          </div>

          {/* Entreprise liee */}
          {contact.company_id && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Entreprise</p>
              <Link
                to={`/companies/${contact.company_id}`}
                className="text-sm text-primary-600 hover:underline"
              >
                Voir l'entreprise
              </Link>
            </div>
          )}

          {/* Metadata */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-sm text-slate-500 space-y-1">
            <p><span className="text-slate-400">Cree le :</span> {new Date(contact.created_at).toLocaleDateString('fr-FR')}</p>
            {contact.department && (
              <p><span className="text-slate-400">Departement :</span> {contact.department}</p>
            )}
            {contact.is_decision_maker && (
              <p className="text-emerald-600 font-medium">Decisionnaire</p>
            )}
          </div>
        </div>
      </div>

      {/* Modal edition */}
      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Modifier le contact"
        size="lg"
      >
        <ContactForm
          contact={contact as Contact}
          onSuccess={() => {
            setEditOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['contact', id] });
          }}
          onCancel={() => setEditOpen(false)}
        />
      </Modal>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
        title="Supprimer le contact"
        message={`Voulez-vous vraiment supprimer ${contact.full_name} ? Cette action est irreversible.`}
        loading={deleteMutation.isPending}
      />

      {/* Modal email */}
      <ComposeModal
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        prefilledContact={contact as Contact}
      />
    </div>
  );
}
