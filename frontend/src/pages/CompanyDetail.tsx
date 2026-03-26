// =============================================================================
// FGA CRM - Page detail d'une entreprise
// =============================================================================

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Globe, Phone, Linkedin, Edit2, Trash2,
  Target, Users, FileSearch, AlertCircle, Clock,
  MapPin, Building2, Save, X, UserPlus, ListTodo,
} from 'lucide-react';

import {
  getCompany, getContacts, getDeals, getActivities, deleteCompany,
  updateCompany, triggerCompanyAudit, createTask,
} from '../api/client';
import type { Contact, Deal, Activity, CompanyAuditResponse } from '../types';
import { COMPANY_SIZE_RANGES, TASK_TYPES, TASK_PRIORITIES } from '../types';
import { Badge, Button, ConfirmDialog, LoadingSpinner, Modal, Tabs } from '../components/ui';
import AuditResultPanel from '../components/audit/AuditResultPanel';
import ContactForm from '../components/contacts/ContactForm';

interface EditForm {
  name: string;
  website: string;
  industry: string;
  description: string;
  size_range: string;
  linkedin_url: string;
  phone: string;
  address_line: string;
  postal_code: string;
  city: string;
  country: string;
}

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
  const [auditSubTab, setAuditSubTab] = useState<'messaging' | 'detailed' | 'geo'>('messaging');
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [contactFormOpen, setContactFormOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: '', type: 'todo', priority: 'medium', due_date: '', contact_id: '' });

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

  const editMutation = useMutation({
    mutationFn: (data: Partial<EditForm>) => updateCompany(id!, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
      setIsEditing(false);
      setEditForm(null);
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

  const taskMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createTask(data),
    onSuccess: () => {
      setTaskOpen(false);
      setTaskForm({ title: '', type: 'todo', priority: 'medium', due_date: '', contact_id: '' });
    },
  });

  const startEditing = () => {
    if (!company) return;
    setEditForm({
      name: company.name,
      website: company.website || '',
      industry: company.industry || '',
      description: company.description || '',
      size_range: company.size_range || '',
      linkedin_url: company.linkedin_url || '',
      phone: company.phone || '',
      address_line: company.address_line || '',
      postal_code: company.postal_code || '',
      city: company.city || '',
      country: company.country || '',
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
      name: editForm.name,
      website: editForm.website || undefined,
      industry: editForm.industry || undefined,
      description: editForm.description || undefined,
      size_range: editForm.size_range || undefined,
      linkedin_url: editForm.linkedin_url || undefined,
      phone: editForm.phone || undefined,
      address_line: editForm.address_line || undefined,
      postal_code: editForm.postal_code || undefined,
      city: editForm.city || undefined,
      country: editForm.country || undefined,
    });
  };

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

  // Grouper les audits par type
  const messagingAudits = auditActivities.filter((a) => a.metadata_?.audit_type === 'messaging');
  const detailedAudits = auditActivities.filter((a) => a.metadata_?.audit_type === 'detailed');
  const geoAudits = auditActivities.filter((a) => a.metadata_?.audit_type === 'geo');

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

      {/* Card principale consolidee */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        {/* En-tete : nom + secteur + actions */}
        <div className="flex items-start justify-between mb-5">
          {isEditing && editForm ? (
            <div>
              <input
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                className="text-xl font-bold text-slate-800 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent w-full"
                placeholder="Nom de l'entreprise"
              />
              <input
                value={editForm.industry}
                onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })}
                className="text-sm text-slate-500 mt-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent w-full"
                placeholder="Secteur d'activite"
              />
            </div>
          ) : (
            <div>
              <h1 className="text-xl font-bold text-slate-800">{company.name}</h1>
              <p className="text-sm text-slate-500 mt-0.5">{company.industry || '—'}</p>
            </div>
          )}
        </div>

        {/* Grille des champs — toujours affiches */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3 text-sm mb-5">
          {isEditing && editForm ? (
            <>
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  value={editForm.website}
                  onChange={(e) => setEditForm({ ...editForm, website: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Site web"
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
                <span className="text-slate-400">Taille :</span>
                <select
                  value={editForm.size_range}
                  onChange={(e) => setEditForm({ ...editForm, size_range: e.target.value })}
                  className="bg-transparent border-b border-slate-300 text-sm focus:border-primary-500 focus:outline-none p-0"
                >
                  <option value="">—</option>
                  {COMPANY_SIZE_RANGES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2 lg:col-span-2">
                <MapPin className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  value={editForm.address_line}
                  onChange={(e) => setEditForm({ ...editForm, address_line: e.target.value })}
                  className="flex-[2] border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Adresse (ex: 12 rue de la Paix)"
                />
                <input
                  value={editForm.postal_code}
                  onChange={(e) => setEditForm({ ...editForm, postal_code: e.target.value })}
                  className="w-20 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="CP"
                />
                <input
                  value={editForm.city}
                  onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Ville"
                />
                <input
                  value={editForm.country}
                  onChange={(e) => setEditForm({ ...editForm, country: e.target.value })}
                  className="flex-1 border-b border-slate-300 focus:border-primary-500 focus:outline-none bg-transparent text-sm"
                  placeholder="Pays"
                />
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cree le :</span>
                <span className="text-slate-700">
                  {new Date(company.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>
              {company.updated_at && company.updated_at !== company.created_at && (
                <div className="flex items-center gap-2">
                  <Edit2 className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Modifie le :</span>
                  <span className="text-slate-700">
                    {new Date(company.updated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </span>
                  {company.updated_by_name && (
                    <span className="text-slate-400">par {company.updated_by_name}</span>
                  )}
                </div>
              )}
              {company.startup_radar_id && (
                <div className="flex items-center gap-2">
                  <FileSearch className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Startup Radar</span>
                </div>
              )}
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Site web :</span>
                {company.website ? (
                  <a href={company.website.startsWith('http') ? company.website : `https://${company.website}`} target="_blank" rel="noopener noreferrer" className="text-slate-700 hover:text-primary-600 truncate">
                    {company.website}
                  </a>
                ) : (
                  <span className="text-slate-300">Non renseigne</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-slate-400 shrink-0" />
                {company.phone ? (
                  <a href={`tel:${company.phone}`} className="text-slate-700 hover:text-primary-600">{company.phone}</a>
                ) : (
                  <span className="text-slate-300">Tel. non renseigne</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Linkedin className="w-4 h-4 text-slate-400 shrink-0" />
                {company.linkedin_url ? (
                  <a href={company.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-slate-700 hover:text-primary-600">
                    LinkedIn
                  </a>
                ) : (
                  <span className="text-slate-300">LinkedIn non renseigne</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Taille :</span>
                <span className="text-slate-700">{company.size_range ? `${company.size_range} employes` : '—'}</span>
              </div>
              <div className="flex items-start gap-2 lg:col-span-2">
                <MapPin className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                <div className="text-sm">
                  <span className="text-slate-400">Adresse :</span>
                  {company.address_line || company.postal_code || company.city || company.country ? (
                    <div className="text-slate-700 mt-0.5 leading-relaxed">
                      {company.address_line && <div>{company.address_line}</div>}
                      {(company.postal_code || company.city) && (
                        <div>{[company.postal_code, company.city].filter(Boolean).join(' ')}</div>
                      )}
                      {company.country && <div>{company.country}</div>}
                    </div>
                  ) : (
                    <span className="text-slate-300 ml-1">—</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-400">Cree le :</span>
                <span className="text-slate-700">
                  {new Date(company.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
                {company.owner_name && (
                  <span className="text-slate-400">par {company.owner_name}</span>
                )}
              </div>
              {company.updated_at && company.updated_at !== company.created_at && (
                <div className="flex items-center gap-2">
                  <Edit2 className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Modifie le :</span>
                  <span className="text-slate-700">
                    {new Date(company.updated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </span>
                  {company.updated_by_name && (
                    <span className="text-slate-400">par {company.updated_by_name}</span>
                  )}
                </div>
              )}
              {company.startup_radar_id && (
                <div className="flex items-center gap-2">
                  <FileSearch className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="text-slate-400">Startup Radar</span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Description */}
        {isEditing && editForm ? (
          <div className="mb-5">
            <textarea
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              className="w-full border border-slate-200 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[60px]"
              placeholder="Description de l'entreprise..."
            />
          </div>
        ) : (
          company.description && (
            <p className="text-sm text-slate-600 border-t border-slate-100 pt-4 mb-5">
              {company.description}
            </p>
          )
        )}

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
              {canAudit && (
                <Button
                  icon={FileSearch}
                  variant="secondary"
                  size="sm"
                  onClick={() => auditMutation.mutate()}
                  disabled={auditMutation.isPending}
                >
                  {auditMutation.isPending ? 'Chargement...' : 'Audit avance'}
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Tabs + bouton ajouter contact */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
          <div className="flex gap-2">
            <Button icon={UserPlus} variant="secondary" size="sm" onClick={() => setContactFormOpen(true)}>
              Ajouter un contact
            </Button>
            <Button icon={ListTodo} variant="secondary" size="sm" onClick={() => setTaskOpen(true)}>
              Ajouter une tache
            </Button>
          </div>
        </div>

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

        {/* Onglet Audit SR — sous-tabs Messaging / Detaille / GEO */}
        {activeTab === 'audit' && (
          <div className="space-y-4">
            {/* Bouton lancer audit + sous-tabs */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
                {([
                  { key: 'messaging' as const, label: 'Messaging', count: messagingAudits.length },
                  { key: 'detailed' as const, label: 'Detaille', count: detailedAudits.length },
                  { key: 'geo' as const, label: 'GEO', count: geoAudits.length },
                ] as const).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setAuditSubTab(tab.key)}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                      auditSubTab === tab.key
                        ? 'bg-white text-slate-800 shadow-sm'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {tab.label}
                    {tab.count > 0 && (
                      <span className="ml-1.5 text-xs text-slate-400">({tab.count})</span>
                    )}
                  </button>
                ))}
              </div>
              {canAudit && (
                <Button
                  icon={FileSearch}
                  variant="secondary"
                  size="sm"
                  onClick={() => auditMutation.mutate()}
                  disabled={auditMutation.isPending}
                >
                  {auditMutation.isPending ? 'Chargement...' : 'Lancer un audit'}
                </Button>
              )}
            </div>

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

            {/* Contenu du sous-tab actif */}
            {(() => {
              const currentAudits =
                auditSubTab === 'messaging' ? messagingAudits :
                auditSubTab === 'detailed' ? detailedAudits :
                geoAudits;

              if (currentAudits.length === 0) {
                return (
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center text-slate-400">
                    <FileSearch className="w-8 h-8 mx-auto mb-2" />
                    <p className="text-sm">
                      Aucun audit {auditSubTab === 'messaging' ? 'messaging' : auditSubTab === 'detailed' ? 'detaille' : 'GEO'} disponible
                    </p>
                  </div>
                );
              }

              return (
                <div className="space-y-4">
                  {currentAudits.map((a) => (
                    a.metadata_ ? (
                      <AuditResultPanel
                        key={a.id}
                        metadata={a.metadata_}
                        subject={a.subject || 'Audit'}
                        createdAt={a.created_at}
                        content={a.content || ''}
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
              );
            })()}
          </div>
        )}
      </div>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
        title="Supprimer l'entreprise"
        message={`Voulez-vous vraiment supprimer ${company.name} ? Cette action est irreversible.`}
        loading={deleteMutation.isPending}
      />

      {/* Modal ajout contact */}
      <Modal
        open={contactFormOpen}
        onClose={() => setContactFormOpen(false)}
        title="Nouveau contact"
        size="lg"
      >
        <ContactForm
          defaultCompanyId={id}
          onSuccess={() => {
            setContactFormOpen(false);
            void queryClient.invalidateQueries({ queryKey: ['contacts', { company_id: id }] });
            setActiveTab('contacts');
          }}
          onCancel={() => setContactFormOpen(false)}
        />
      </Modal>

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
              contact_id: taskForm.contact_id || undefined,
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

          {/* Dropdown contact de l'entreprise (optionnel) */}
          {contacts.length > 0 && (
            <div>
              <label htmlFor="task-contact" className="block text-sm font-medium text-slate-700 mb-1">Contact associe (optionnel)</label>
              <select
                id="task-contact"
                value={taskForm.contact_id}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, contact_id: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Aucun</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>{c.full_name}</option>
                ))}
              </select>
            </div>
          )}

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
