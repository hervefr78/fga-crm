// =============================================================================
// FGA CRM - Page detail d'un contact
// =============================================================================

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Mail, Phone, Linkedin, Edit2, Trash2,
  Calendar, Target, CheckCircle2, ListPlus, Building2, User,
  Clock, Briefcase, Star, Save, X,
} from 'lucide-react';

import {
  getContact, getActivities, getDeals, getTasks, deleteContact, createTask, updateContact,
} from '../api/client';
import type { Contact, Activity, Deal, Task } from '../types';
import { TASK_TYPES, TASK_PRIORITIES, JOB_LEVELS } from '../types';
import { Badge, Button, ConfirmDialog, LoadingSpinner, Modal, Tabs } from '../components/ui';
import ComposeModal from '../components/email/ComposeModal';

interface EditForm {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  title: string;
  linkedin_url: string;
  department: string;
  source: string;
  status: string;
  job_level: string;
  is_decision_maker: boolean;
}

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
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [composeOpen, setComposeOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: '', type: 'todo', priority: 'medium', due_date: '' });

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

  const taskMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createTask(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks', { contact_id: id }] });
      setTaskOpen(false);
      setTaskForm({ title: '', type: 'todo', priority: 'medium', due_date: '' });
      setActiveTab('tasks');
    },
  });

  const editMutation = useMutation({
    mutationFn: (data: Partial<EditForm>) => updateContact(id!, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contact', id] });
      setIsEditing(false);
      setEditForm(null);
    },
  });

  const startEditing = () => {
    if (!contact) return;
    setEditForm({
      first_name: contact.first_name,
      last_name: contact.last_name,
      email: contact.email || '',
      phone: contact.phone || '',
      title: contact.title || '',
      linkedin_url: contact.linkedin_url || '',
      department: contact.department || '',
      source: contact.source || '',
      status: contact.status,
      job_level: contact.job_level || '',
      is_decision_maker: contact.is_decision_maker,
    });
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditForm(null);
  };

  const saveEditing = () => {
    if (!editForm) return;
    editMutation.mutate({
      ...editForm,
      email: editForm.email || undefined,
      phone: editForm.phone || undefined,
      title: editForm.title || undefined,
      linkedin_url: editForm.linkedin_url || undefined,
      department: editForm.department || undefined,
      source: editForm.source || undefined,
      job_level: editForm.job_level || undefined,
    });
  };

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

      {/* Card principale consolidee */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        {/* En-tete : nom + statut + actions */}
        <div className="flex items-start justify-between mb-5">
          {isEditing && editForm ? (
            <div className="flex gap-3">
              <input
                value={editForm.first_name}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                className="text-xl font-bold text-slate-800 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent"
                placeholder="Prenom"
              />
              <input
                value={editForm.last_name}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                className="text-xl font-bold text-slate-800 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent"
                placeholder="Nom"
              />
            </div>
          ) : (
            <div>
              <h1 className="text-xl font-bold text-slate-800">{contact.full_name}</h1>
              <p className="text-sm text-slate-500 mt-0.5">{contact.title || '—'}</p>
            </div>
          )}
          <div className="flex items-center gap-2">
            {isEditing && editForm ? (
              <select
                value={editForm.status}
                onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                className="text-xs px-2 py-1 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {Object.entries(STATUS_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            ) : (
              <Badge variant={STATUS_COLORS[contact.status] || 'default'}>
                {STATUS_LABELS[contact.status] || contact.status}
              </Badge>
            )}
            {isEditing && editForm ? (
              <label className="flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={editForm.is_decision_maker}
                  onChange={(e) => setEditForm({ ...editForm, is_decision_maker: e.target.checked })}
                  className="rounded border-slate-300"
                />
                Decisionnaire
              </label>
            ) : (
              contact.is_decision_maker && <Badge variant="success">Decisionnaire</Badge>
            )}
          </div>
        </div>

        {/* Grille des champs — toujours affiches */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3 text-sm mb-5">
          {isEditing && editForm ? (
            <>
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Fonction / Titre"
                />
              </div>
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Email"
                  type="email"
                />
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  value={editForm.phone}
                  onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Telephone"
                />
              </div>
              <div className="flex items-center gap-2">
                <Linkedin className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  value={editForm.linkedin_url}
                  onChange={(e) => setEditForm({ ...editForm, linkedin_url: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="URL LinkedIn"
                />
              </div>
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Departement :</span>
                <input
                  value={editForm.department}
                  onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Departement"
                />
              </div>
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Niveau :</span>
                <select
                  value={editForm.job_level}
                  onChange={(e) => setEditForm({ ...editForm, job_level: e.target.value })}
                  className="bg-transparent border-b border-slate-300 text-sm focus:border-primary-500 focus:outline-none p-0"
                >
                  <option value="">—</option>
                  {JOB_LEVELS.map((jl) => (
                    <option key={jl.value} value={jl.value}>{jl.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Source :</span>
                <input
                  value={editForm.source}
                  onChange={(e) => setEditForm({ ...editForm, source: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Source"
                />
              </div>
              <div className="flex items-center gap-2">
                <Star className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Score :</span>
                <span className="text-slate-700">{contact.lead_score}/100</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cree le :</span>
                <span className="text-slate-700">
                  {new Date(contact.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>
              {contact.updated_at && contact.updated_at !== contact.created_at && (
                <div className="flex items-center gap-2">
                  <Edit2 className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Modifie le :</span>
                  <span className="text-slate-700">
                    {new Date(contact.updated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </span>
                  {contact.updated_by_name && (
                    <span className="text-slate-400">par {contact.updated_by_name}</span>
                  )}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-slate-400 shrink-0" />
                {contact.email ? (
                  <a href={`mailto:${contact.email}`} className="text-slate-700 hover:text-primary-600 truncate">{contact.email}</a>
                ) : (
                  <span className="text-slate-300">Email non renseigne</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-slate-400 shrink-0" />
                {contact.phone ? (
                  <a href={`tel:${contact.phone}`} className="text-slate-700 hover:text-primary-600">{contact.phone}</a>
                ) : (
                  <span className="text-slate-300">Tel. non renseigne</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Linkedin className="w-4 h-4 text-slate-400 shrink-0" />
                {contact.linkedin_url ? (
                  <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-slate-700 hover:text-primary-600 truncate">
                    LinkedIn
                  </a>
                ) : (
                  <span className="text-slate-300">LinkedIn non renseigne</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-slate-400 shrink-0" />
                {contact.company_id ? (
                  <Link to={`/companies/${contact.company_id}`} className="text-primary-600 hover:underline truncate">
                    Voir l'entreprise
                  </Link>
                ) : (
                  <span className="text-slate-300">Entreprise non rattachee</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Departement :</span>
                <span className="text-slate-700">{contact.department || '—'}</span>
              </div>
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Niveau :</span>
                <span className="text-slate-700">{contact.job_level || '—'}</span>
              </div>
              <div className="flex items-center gap-2">
                <Star className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Score :</span>
                <span className="text-slate-700">{contact.lead_score}/100</span>
              </div>
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Source :</span>
                <span className="text-slate-700">{contact.source || '—'}</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cree le :</span>
                <span className="text-slate-700">
                  {new Date(contact.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
                {contact.owner_name && (
                  <span className="text-slate-400">par {contact.owner_name}</span>
                )}
              </div>
              {contact.updated_at && contact.updated_at !== contact.created_at && (
                <div className="flex items-center gap-2">
                  <Edit2 className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Modifie le :</span>
                  <span className="text-slate-700">
                    {new Date(contact.updated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </span>
                  {contact.updated_by_name && (
                    <span className="text-slate-400">par {contact.updated_by_name}</span>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Boutons d'action */}
        <div className="flex flex-wrap gap-2 pt-3 border-t border-slate-100">
          {isEditing ? (
            <>
              <Button icon={Save} variant="primary" size="sm" onClick={saveEditing} loading={editMutation.isPending}>
                Enregistrer
              </Button>
              <Button icon={X} variant="secondary" size="sm" onClick={cancelEditing}>
                Annuler
              </Button>
            </>
          ) : (
            <>
              {contact.email && (
                <Button icon={Mail} variant="primary" size="sm" onClick={() => setComposeOpen(true)}>
                  Envoyer un email
                </Button>
              )}
              <Button icon={Edit2} variant="secondary" size="sm" onClick={startEditing}>
                Modifier
              </Button>
              <Button icon={Trash2} variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
                Supprimer
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Tabs + bouton ajouter tache */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
          <Button icon={ListPlus} variant="secondary" size="sm" onClick={() => setTaskOpen(true)}>
            Ajouter une tache
          </Button>
        </div>

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

      {/* Modal ajout tache */}
      <Modal
        open={taskOpen}
        onClose={() => setTaskOpen(false)}
        title="Nouvelle tache"
        size="md"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            taskMutation.mutate({
              title: taskForm.title,
              type: taskForm.type,
              priority: taskForm.priority,
              contact_id: id,
              due_date: taskForm.due_date || undefined,
            });
          }}
          className="space-y-4"
        >
          <div>
            <label htmlFor="task-title" className="block text-sm font-medium text-slate-700 mb-1">Titre</label>
            <input
              id="task-title"
              type="text"
              required
              maxLength={500}
              value={taskForm.title}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, title: e.target.value }))}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Ex: Appeler pour suivi..."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="task-type" className="block text-sm font-medium text-slate-700 mb-1">Type</label>
              <select
                id="task-type"
                value={taskForm.type}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, type: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {TASK_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="task-priority" className="block text-sm font-medium text-slate-700 mb-1">Priorite</label>
              <select
                id="task-priority"
                value={taskForm.priority}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, priority: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {TASK_PRIORITIES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="task-due-date" className="block text-sm font-medium text-slate-700 mb-1">Echeance (optionnel)</label>
            <input
              id="task-due-date"
              type="date"
              value={taskForm.due_date}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, due_date: e.target.value }))}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setTaskOpen(false)} type="button">
              Annuler
            </Button>
            <Button type="submit" loading={taskMutation.isPending}>
              Creer la tache
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
