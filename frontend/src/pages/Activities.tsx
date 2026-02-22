// =============================================================================
// FGA CRM - Activities Page (liste + CRUD)
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity as ActivityIcon,
  Plus,
  Trash2,
  Mail,
  Phone,
  Calendar,
  StickyNote,
  Linkedin,
  CheckSquare,
} from 'lucide-react';

import { getActivities, deleteActivity } from '../api/client';
import type { Activity } from '../types';
import { ACTIVITY_TYPES } from '../types';
import {
  Modal,
  SearchInput,
  Pagination,
  LoadingSpinner,
  EmptyState,
  ConfirmDialog,
  Badge,
  Button,
  Select,
} from '../components/ui';
import ActivityForm from '../components/activities/ActivityForm';

// ---------- Badge maps ----------

const TYPE_COLORS: Record<string, 'default' | 'info' | 'success' | 'warning'> = {
  email: 'info',
  call: 'success',
  meeting: 'warning',
  note: 'default',
  linkedin: 'info',
  task: 'success',
};

const TYPE_LABELS: Record<string, string> = {
  email: 'Email',
  call: 'Appel',
  meeting: 'Meeting',
  note: 'Note',
  linkedin: 'LinkedIn',
  task: 'Tâche',
};

const TYPE_ICONS: Record<string, React.ElementType> = {
  email: Mail,
  call: Phone,
  meeting: Calendar,
  note: StickyNote,
  linkedin: Linkedin,
  task: CheckSquare,
};

export default function ActivitiesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState('');

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingActivity, setEditingActivity] = useState<Activity | undefined>(undefined);
  const [deletingActivity, setDeletingActivity] = useState<Activity | null>(null);

  // Construire les params de requete
  const queryParams: Record<string, unknown> = { page, size: 25 };
  if (search) queryParams.search = search;
  if (filterType) queryParams.type = filterType;

  const { data, isLoading } = useQuery({
    queryKey: ['activities', queryParams],
    queryFn: () => getActivities(queryParams),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteActivity(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['activities'] });
      setDeletingActivity(null);
    },
  });

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const openCreate = () => {
    setEditingActivity(undefined);
    setFormOpen(true);
  };

  const openEdit = (activity: Activity) => {
    setEditingActivity(activity);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingActivity(undefined);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncate = (text: string | null, maxLen: number) => {
    if (!text) return '—';
    return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Activités</h1>
          <p className="text-slate-400 text-sm mt-1">{data?.total || 0} activités au total</p>
        </div>
        <Button icon={Plus} onClick={openCreate}>
          Nouvelle activité
        </Button>
      </div>

      {/* Recherche */}
      <div className="mb-4">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Rechercher une activité..."
        />
      </div>

      {/* Filtre type */}
      <div className="mb-5 max-w-xs">
        <Select
          value={filterType}
          onChange={(v) => { setFilterType(v); setPage(1); }}
          options={[...ACTIVITY_TYPES]}
          placeholder="Tous les types"
        />
      </div>

      {/* Tableau */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.items?.length ? (
          <EmptyState icon={ActivityIcon} message="Aucune activité trouvée" />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Sujet</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Contenu</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Date</th>
                  <th className="px-6 py-3 w-12" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((activity: Activity) => {
                  const Icon = TYPE_ICONS[activity.type] || ActivityIcon;
                  return (
                    <tr
                      key={activity.id}
                      onClick={() => openEdit(activity)}
                      className="hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4 text-slate-400" />
                          <Badge variant={TYPE_COLORS[activity.type] || 'default'}>
                            {TYPE_LABELS[activity.type] || activity.type}
                          </Badge>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-700">
                        {activity.subject || '—'}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-500">
                        {truncate(activity.content, 60)}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-500">
                        {formatDate(activity.created_at)}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingActivity(activity);
                          }}
                          className="p-1 text-slate-300 hover:text-red-500 rounded transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
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
        title={editingActivity ? 'Modifier l\'activité' : 'Nouvelle activité'}
        size="lg"
      >
        <ActivityForm
          activity={editingActivity}
          onSuccess={closeForm}
          onCancel={closeForm}
        />
      </Modal>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={!!deletingActivity}
        onClose={() => setDeletingActivity(null)}
        onConfirm={() => deletingActivity && deleteMutation.mutate(deletingActivity.id)}
        title="Supprimer l'activité"
        message={`Voulez-vous vraiment supprimer cette activité ? Cette action est irréversible.`}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
