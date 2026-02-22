// =============================================================================
// FGA CRM - Tasks Page (liste + CRUD + toggle completion)
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ListTodo, Plus, Trash2 } from 'lucide-react';

import { getTasks, deleteTask, toggleTaskCompletion } from '../api/client';
import type { Task } from '../types';
import { TASK_TYPES, TASK_PRIORITIES } from '../types';
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
import TaskForm from '../components/tasks/TaskForm';

// ---------- Badge maps ----------

const TYPE_COLORS: Record<string, 'default' | 'info' | 'success' | 'warning'> = {
  todo: 'default',
  call: 'info',
  email: 'warning',
  meeting: 'success',
};

const TYPE_LABELS: Record<string, string> = {
  todo: 'À faire',
  call: 'Appel',
  email: 'Email',
  meeting: 'Meeting',
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

// ---------- Helpers ----------

const COMPLETED_OPTIONS = [
  { value: 'all', label: 'Toutes' },
  { value: 'false', label: 'En cours' },
  { value: 'true', label: 'Terminées' },
] as const;

function formatDueDate(dateStr: string | null, isCompleted: boolean): { text: string; className: string } {
  if (!dateStr) return { text: '—', className: 'text-slate-400' };

  const date = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const formatted = date.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
  });

  if (isCompleted) return { text: formatted, className: 'text-slate-400 line-through' };

  const dueDay = new Date(date);
  dueDay.setHours(0, 0, 0, 0);

  if (dueDay < today) return { text: formatted, className: 'text-red-600 font-medium' };
  if (dueDay.getTime() === today.getTime()) return { text: 'Aujourd\'hui', className: 'text-amber-600 font-medium' };

  return { text: formatted, className: 'text-slate-500' };
}

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  // Filtres
  const [filterType, setFilterType] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [filterCompleted, setFilterCompleted] = useState('all');

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | undefined>(undefined);
  const [deletingTask, setDeletingTask] = useState<Task | null>(null);

  // Construire les params de requete
  const queryParams: Record<string, unknown> = { page, size: 25 };
  if (search) queryParams.search = search;
  if (filterType) queryParams.type = filterType;
  if (filterPriority) queryParams.priority = filterPriority;
  if (filterCompleted !== 'all') queryParams.is_completed = filterCompleted;

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', queryParams],
    queryFn: () => getTasks(queryParams),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTask(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setDeletingTask(null);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_completed }: { id: string; is_completed: boolean }) =>
      toggleTaskCompletion(id, is_completed),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const openCreate = () => {
    setEditingTask(undefined);
    setFormOpen(true);
  };

  const openEdit = (task: Task) => {
    setEditingTask(task);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingTask(undefined);
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Tâches</h1>
          <p className="text-slate-400 text-sm mt-1">{data?.total || 0} tâches au total</p>
        </div>
        <Button icon={Plus} onClick={openCreate}>
          Nouvelle tâche
        </Button>
      </div>

      {/* Recherche */}
      <div className="mb-4">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Rechercher une tâche..."
        />
      </div>

      {/* Filtres */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <Select
          value={filterType}
          onChange={(v) => { setFilterType(v); setPage(1); }}
          options={[...TASK_TYPES]}
          placeholder="Tous les types"
        />
        <Select
          value={filterPriority}
          onChange={(v) => { setFilterPriority(v); setPage(1); }}
          options={[...TASK_PRIORITIES]}
          placeholder="Toutes les priorités"
        />
        <Select
          value={filterCompleted}
          onChange={(v) => { setFilterCompleted(v); setPage(1); }}
          options={[...COMPLETED_OPTIONS]}
        />
      </div>

      {/* Tableau */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.items?.length ? (
          <EmptyState icon={ListTodo} message="Aucune tâche trouvée" />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 w-10" />
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Titre</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Priorité</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide">Échéance</th>
                  <th className="px-4 py-3 w-12" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((task: Task) => {
                  const due = formatDueDate(task.due_date, task.is_completed);
                  return (
                    <tr
                      key={task.id}
                      onClick={() => openEdit(task)}
                      className="hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      {/* Checkbox completion */}
                      <td className="px-4 py-4">
                        <input
                          type="checkbox"
                          checked={task.is_completed}
                          onChange={() =>
                            toggleMutation.mutate({
                              id: task.id,
                              is_completed: !task.is_completed,
                            })
                          }
                          onClick={(e) => e.stopPropagation()}
                          className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
                        />
                      </td>
                      <td className="px-4 py-4">
                        <p className={`text-sm font-medium ${task.is_completed ? 'text-slate-400 line-through' : 'text-slate-700'}`}>
                          {task.title}
                        </p>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant={TYPE_COLORS[task.type] || 'default'}>
                          {TYPE_LABELS[task.type] || task.type}
                        </Badge>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant={PRIORITY_COLORS[task.priority] || 'default'}>
                          {PRIORITY_LABELS[task.priority] || task.priority}
                        </Badge>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`text-sm ${due.className}`}>{due.text}</span>
                      </td>
                      <td className="px-4 py-4">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingTask(task);
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
        title={editingTask ? 'Modifier la tâche' : 'Nouvelle tâche'}
        size="lg"
      >
        <TaskForm
          task={editingTask}
          onSuccess={closeForm}
          onCancel={closeForm}
        />
      </Modal>

      {/* Dialog suppression */}
      <ConfirmDialog
        open={!!deletingTask}
        onClose={() => setDeletingTask(null)}
        onConfirm={() => deletingTask && deleteMutation.mutate(deletingTask.id)}
        title="Supprimer la tâche"
        message={`Voulez-vous vraiment supprimer « ${deletingTask?.title} » ? Cette action est irréversible.`}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
