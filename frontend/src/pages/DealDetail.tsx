// =============================================================================
// FGA CRM - Page detail d'un deal
// =============================================================================

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Edit2, Trash2, Save, X, Calendar,
  DollarSign, Percent, Clock, Building2, User, ListPlus,
  CheckCircle2, FileText, AlertCircle,
} from 'lucide-react';

import {
  getDeal, updateDeal, deleteDeal, getActivities, getTasks,
  createTask, getCompanies, getContacts,
} from '../api/client';
import type { Activity, Task, Company, Contact, PaginatedResponse } from '../types';
import { DEAL_STAGES, DEAL_PRIORITIES, DEAL_PRICING_TYPES, PRICING_PERIOD_MONTHS, TASK_TYPES, TASK_PRIORITIES } from '../types';
import { Badge, Button, ConfirmDialog, LoadingSpinner, Modal, Tabs } from '../components/ui';

// -- Mappings d'affichage --

const STAGE_COLORS: Record<string, 'default' | 'info' | 'success' | 'danger' | 'warning'> = {
  new: 'default',
  contacted: 'info',
  meeting: 'info',
  proposal: 'warning',
  negotiation: 'warning',
  won: 'success',
  lost: 'danger',
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

const PRIORITY_COLORS: Record<string, 'default' | 'info' | 'warning' | 'danger'> = {
  low: 'default',
  medium: 'info',
  high: 'warning',
  urgent: 'danger',
};

const PRIORITY_LABELS: Record<string, string> = {
  low: 'Basse',
  medium: 'Moyenne',
  high: 'Haute',
  urgent: 'Urgente',
};

// Mapping pricing_type -> label affichage (depuis DEAL_PRICING_TYPES)
const PRICING_LABELS: Record<string, string> = Object.fromEntries(
  DEAL_PRICING_TYPES.map((p) => [p.value, p.label]),
);

const ACTIVITY_LABELS: Record<string, string> = {
  email: 'Email',
  call: 'Appel',
  meeting: 'Meeting',
  note: 'Note',
  linkedin: 'LinkedIn',
  task: 'Tache',
  audit: 'Audit',
};

// -- Interface d'edition inline --

interface EditForm {
  title: string;
  stage: string;
  amount: string;
  currency: string;
  probability: string;
  priority: string;
  expected_close_date: string;
  company_id: string;
  contact_id: string;
  description: string;
  // Tarification (DC10 : noms exacts du backend)
  pricing_type: string;
  recurring_amount: string;
  commitment_months: string;
}

// Label "court" pour le champ recurrent (entre parentheses) — duplique de DealForm.tsx
// pour rester coherent visuellement sans abstraire deux UX differentes
const PRICING_PERIOD_LABEL: Record<string, string> = {
  monthly: 'mensuel',
  quarterly: 'trimestriel',
  biannual: 'semestriel',
  annual: 'annuel',
};

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('activities');
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: '', type: 'todo', priority: 'medium', due_date: '' });

  // -- Queries --

  const { data: deal, isLoading } = useQuery({
    queryKey: ['deal', id],
    queryFn: () => getDeal(id!),
    enabled: !!id,
  });

  const { data: activitiesData } = useQuery({
    queryKey: ['activities', { deal_id: id }],
    queryFn: () => getActivities({ deal_id: id, size: 50 }),
    enabled: !!id,
  });

  const { data: tasksData } = useQuery({
    queryKey: ['tasks', { deal_id: id }],
    queryFn: () => getTasks({ deal_id: id, size: 50 }),
    enabled: !!id,
  });

  // Dropdowns pour edition (entreprise / contact)
  const { data: companiesData } = useQuery<PaginatedResponse<Company>>({
    queryKey: ['companies', { size: 100 }],
    queryFn: () => getCompanies({ size: 100 }),
    enabled: isEditing,
  });

  const { data: contactsData } = useQuery<PaginatedResponse<Contact>>({
    queryKey: ['contacts', { size: 100 }],
    queryFn: () => getContacts({ size: 100 }),
    enabled: isEditing,
  });

  // -- Mutations --

  const deleteMutation = useMutation({
    mutationFn: () => deleteDeal(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['deals'] });
      navigate('/pipeline');
    },
  });

  const editMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateDeal(id!, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['deal', id] });
      void queryClient.invalidateQueries({ queryKey: ['deals'] });
      setIsEditing(false);
      setEditForm(null);
    },
  });

  const taskMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createTask(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks', { deal_id: id }] });
      setTaskOpen(false);
      setTaskForm({ title: '', type: 'todo', priority: 'medium', due_date: '' });
      setActiveTab('tasks');
    },
  });

  // -- Edition inline --

  const startEditing = () => {
    if (!deal) return;
    setEditForm({
      title: deal.title,
      stage: deal.stage,
      amount: deal.amount?.toString() || '',
      currency: deal.currency,
      probability: deal.probability?.toString() || '0',
      priority: deal.priority,
      expected_close_date: deal.expected_close_date || '',
      company_id: deal.company_id || '',
      contact_id: deal.contact_id || '',
      description: deal.description || '',
      pricing_type: deal.pricing_type,
      recurring_amount: deal.recurring_amount?.toString() ?? '',
      commitment_months: deal.commitment_months?.toString() ?? '',
    });
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditForm(null);
    setEditError(null);
  };

  const saveEditing = () => {
    if (!editForm) return;
    setEditError(null);

    // Validation cross-field : pricing recurrent → recurring_amount obligatoire (DC8 : meme regle que DealForm)
    if (editForm.pricing_type !== 'one_shot' && !editForm.recurring_amount.trim()) {
      setEditError('Le montant unitaire est obligatoire pour un abonnement.');
      return;
    }

    const data: Record<string, unknown> = {
      title: editForm.title.trim(),
      stage: editForm.stage,
      currency: editForm.currency,
      priority: editForm.priority,
      probability: parseInt(editForm.probability, 10) || 0,
      pricing_type: editForm.pricing_type,
    };
    if (editForm.expected_close_date) data.expected_close_date = editForm.expected_close_date;
    if (editForm.company_id) data.company_id = editForm.company_id;
    else data.company_id = null;
    if (editForm.contact_id) data.contact_id = editForm.contact_id;
    else data.contact_id = null;
    if (editForm.description.trim()) data.description = editForm.description.trim();
    else data.description = null;

    // Tarification — symetrique de DealForm.tsx (DC8 : meme logique de calcul amount)
    if (editForm.pricing_type === 'one_shot') {
      // One-shot : amount classique, on remet a null les champs recurrents
      // (DealUpdate Pydantic accepte null pour nettoyer les anciens recurring values)
      data.recurring_amount = null;
      data.commitment_months = null;
      if (editForm.amount.trim()) data.amount = parseFloat(editForm.amount);
    } else {
      // Recurrent : recurring_amount + commitment_months, et amount = total contrat
      if (editForm.recurring_amount.trim()) {
        data.recurring_amount = parseFloat(editForm.recurring_amount);
      }
      if (editForm.commitment_months.trim()) {
        data.commitment_months = parseInt(editForm.commitment_months, 10);
      }
      // Recalcul du montant total (nb periodes * recurring) pour KPI agreges
      if (editForm.recurring_amount.trim() && editForm.commitment_months.trim()) {
        const months = PRICING_PERIOD_MONTHS[editForm.pricing_type] || 1;
        const totalPeriods = parseInt(editForm.commitment_months, 10) / months;
        data.amount = parseFloat(editForm.recurring_amount) * totalPeriods;
      }
    }

    editMutation.mutate(data);
  };

  // -- Render --

  if (isLoading) return <LoadingSpinner />;
  if (!deal) {
    return (
      <div className="p-8">
        <p className="text-slate-500">Deal non trouve.</p>
        <Link to="/pipeline" className="text-primary-600 hover:underline text-sm mt-2 inline-block">
          Retour au pipeline
        </Link>
      </div>
    );
  }

  const activities: Activity[] = activitiesData?.items || [];
  const tasks: Task[] = tasksData?.items || [];

  const companyOptions = (companiesData?.items || []).map((c) => ({ value: c.id, label: c.name }));
  const contactOptions = (contactsData?.items || []).map((c) => ({ value: c.id, label: c.full_name }));

  const tabs = [
    { key: 'activities', label: 'Activites', count: activities.length },
    { key: 'tasks', label: 'Taches', count: tasks.length },
  ];

  const formatAmount = (amount: number | null, currency: string) => {
    if (amount === null) return '—';
    return `${amount.toLocaleString('fr-FR')} ${currency}`;
  };

  return (
    <div className="p-8">
      {/* Bouton retour */}
      <button
        onClick={() => navigate('/pipeline')}
        className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Pipeline
      </button>

      {/* Card principale */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        {/* En-tete : titre + stage + priority */}
        <div className="flex items-start justify-between mb-5">
          {isEditing && editForm ? (
            <input
              value={editForm.title}
              onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
              className="text-xl font-bold text-slate-800 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent flex-1 mr-4"
              placeholder="Titre du deal"
            />
          ) : (
            <h1 className="text-xl font-bold text-slate-800">{deal.title}</h1>
          )}
          <div className="flex items-center gap-2 shrink-0">
            {isEditing && editForm ? (
              <>
                <select
                  value={editForm.stage}
                  onChange={(e) => setEditForm({ ...editForm, stage: e.target.value })}
                  className="text-xs px-2 py-1 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {DEAL_STAGES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
                <select
                  value={editForm.priority}
                  onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                  className="text-xs px-2 py-1 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {DEAL_PRIORITIES.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </>
            ) : (
              <>
                <Badge variant={STAGE_COLORS[deal.stage] || 'default'}>
                  {STAGE_LABELS[deal.stage] || deal.stage}
                </Badge>
                <Badge variant={PRIORITY_COLORS[deal.priority] || 'default'}>
                  {PRIORITY_LABELS[deal.priority] || deal.priority}
                </Badge>
              </>
            )}
          </div>
        </div>

        {/* Erreur de validation en mode edition */}
        {isEditing && editError && (
          <div className="mb-4 flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {editError}
          </div>
        )}

        {/* Selecteur pricing_type — affiche uniquement en mode edition (DC8 : pattern identique a DealForm.tsx) */}
        {isEditing && editForm && (
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">Type de tarification</label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {DEAL_PRICING_TYPES.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setEditForm({ ...editForm, pricing_type: p.value })}
                  className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                    editForm.pricing_type === p.value
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Grille des champs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3 text-sm mb-5">
          {isEditing && editForm ? (
            <>
              {/* Montant (one_shot uniquement) */}
              {editForm.pricing_type === 'one_shot' && (
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Montant :</span>
                  <input
                    type="number"
                    value={editForm.amount}
                    onChange={(e) => setEditForm({ ...editForm, amount: e.target.value })}
                    className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                    placeholder="0"
                    min="0"
                    step="0.01"
                  />
                </div>
              )}
              {/* Montant unitaire (recurrent uniquement) */}
              {editForm.pricing_type !== 'one_shot' && (
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">
                    Montant {PRICING_PERIOD_LABEL[editForm.pricing_type] || ''} :
                  </span>
                  <input
                    type="number"
                    value={editForm.recurring_amount}
                    onChange={(e) => setEditForm({ ...editForm, recurring_amount: e.target.value })}
                    className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                    placeholder="500"
                    min="0"
                    step="0.01"
                  />
                </div>
              )}
              {/* Engagement (recurrent uniquement) */}
              {editForm.pricing_type !== 'one_shot' && (
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Engagement :</span>
                  <input
                    type="number"
                    value={editForm.commitment_months}
                    onChange={(e) => setEditForm({ ...editForm, commitment_months: e.target.value })}
                    className="w-20 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                    placeholder="12"
                    min="1"
                    max="120"
                  />
                  <span className="text-slate-400">mois</span>
                </div>
              )}
              {/* Devise */}
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Devise :</span>
                <input
                  value={editForm.currency}
                  onChange={(e) => setEditForm({ ...editForm, currency: e.target.value })}
                  className="w-16 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  maxLength={3}
                />
              </div>
              {/* Probabilite */}
              <div className="flex items-center gap-2">
                <Percent className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Probabilite :</span>
                <input
                  type="number"
                  value={editForm.probability}
                  onChange={(e) => setEditForm({ ...editForm, probability: e.target.value })}
                  className="w-16 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  min="0"
                  max="100"
                />
                <span className="text-slate-400">%</span>
              </div>
              {/* Date de cloture */}
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cloture :</span>
                <input
                  type="date"
                  value={editForm.expected_close_date}
                  onChange={(e) => setEditForm({ ...editForm, expected_close_date: e.target.value })}
                  className="border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                />
              </div>
              {/* Entreprise */}
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Entreprise :</span>
                <select
                  value={editForm.company_id}
                  onChange={(e) => setEditForm({ ...editForm, company_id: e.target.value })}
                  className="flex-1 bg-transparent border-b border-slate-300 text-sm focus:border-primary-500 focus:outline-none p-0"
                >
                  <option value="">Aucune</option>
                  {companyOptions.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              {/* Contact */}
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Contact :</span>
                <select
                  value={editForm.contact_id}
                  onChange={(e) => setEditForm({ ...editForm, contact_id: e.target.value })}
                  className="flex-1 bg-transparent border-b border-slate-300 text-sm focus:border-primary-500 focus:outline-none p-0"
                >
                  <option value="">Aucun</option>
                  {contactOptions.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              {/* Date de creation (read-only) */}
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cree le :</span>
                <span className="text-slate-700">
                  {new Date(deal.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>
            </>
          ) : (
            <>
              {/* Montant */}
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Montant :</span>
                <span className="text-slate-700 font-medium">{formatAmount(deal.amount, deal.currency)}</span>
              </div>
              {/* Probabilite */}
              <div className="flex items-center gap-2">
                <Percent className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Probabilite :</span>
                <span className="text-slate-700">{deal.probability}%</span>
              </div>
              {/* Date de cloture */}
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cloture :</span>
                <span className="text-slate-700">
                  {deal.expected_close_date
                    ? new Date(deal.expected_close_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
                    : '—'}
                </span>
              </div>
              {/* Date de cloture effective (uniquement quand le deal est won/lost) */}
              {(deal.stage === 'won' || deal.stage === 'lost') && deal.actual_close_date && (
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Clôturé le :</span>
                  <span className="text-slate-700 font-medium">
                    {new Date(deal.actual_close_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </span>
                </div>
              )}
              {/* Entreprise */}
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Entreprise :</span>
                {deal.company_id ? (
                  <Link to={`/companies/${deal.company_id}`} className="text-primary-600 hover:underline truncate">
                    Voir l'entreprise
                  </Link>
                ) : (
                  <span className="text-slate-300">—</span>
                )}
              </div>
              {/* Contact */}
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Contact :</span>
                {deal.contact_id ? (
                  <Link to={`/contacts/${deal.contact_id}`} className="text-primary-600 hover:underline truncate">
                    Voir le contact
                  </Link>
                ) : (
                  <span className="text-slate-300">—</span>
                )}
              </div>
              {/* Date de creation */}
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cree le :</span>
                <span className="text-slate-700">
                  {new Date(deal.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>
              {/* Tarification (read-only en mode lecture, displaye en mode edit aussi pour info) */}
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Tarification :</span>
                <span className="text-slate-700">{PRICING_LABELS[deal.pricing_type] || deal.pricing_type}</span>
              </div>
              {deal.pricing_type !== 'one_shot' && deal.recurring_amount !== null && (
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Montant unitaire :</span>
                  <span className="text-slate-700">
                    {deal.recurring_amount.toLocaleString('fr-FR')} {deal.currency}
                  </span>
                </div>
              )}
              {deal.pricing_type !== 'one_shot' && deal.commitment_months !== null && (
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Engagement :</span>
                  <span className="text-slate-700">{deal.commitment_months} mois</span>
                </div>
              )}
              {/* MRR calcule pour les deals recurrents (recurring_amount / period_months) */}
              {deal.pricing_type !== 'one_shot' && deal.recurring_amount !== null && PRICING_PERIOD_MONTHS[deal.pricing_type] && (
                <div className="flex items-center gap-2">
                  <Percent className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">MRR :</span>
                  <span className="text-slate-700 font-medium">
                    {(deal.recurring_amount / PRICING_PERIOD_MONTHS[deal.pricing_type]).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} {deal.currency}/mois
                  </span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Description */}
        {isEditing && editForm ? (
          <div className="mb-5">
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <FileText className="w-4 h-4" /> Description
            </label>
            <textarea
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[80px]"
              placeholder="Notes sur le deal..."
            />
          </div>
        ) : deal.description ? (
          <div className="mb-5">
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <FileText className="w-4 h-4" /> Description
            </div>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{deal.description}</p>
          </div>
        ) : null}

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
        title="Supprimer le deal"
        message={`Voulez-vous vraiment supprimer « ${deal.title} » ? Cette action est irreversible.`}
        loading={deleteMutation.isPending}
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
              deal_id: id,
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
              placeholder="Ex: Preparer la proposition commerciale..."
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
