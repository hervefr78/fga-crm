// =============================================================================
// FGA CRM - Page Admin Utilisateurs
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Shield, UserCheck, UserX, Users, Plus } from 'lucide-react';
import {
  Badge,
  SearchInput,
  Pagination,
  LoadingSpinner,
  EmptyState,
  ConfirmDialog,
  Modal,
  Button,
  Input,
} from '../components/ui';
import FilterBar, { type FilterDef } from '../components/ui/FilterBar';
import { getUsers, updateUserRole, toggleUserActive, createUser } from '../api/client';
import { USER_ROLES, type User, type PaginatedResponse } from '../types';
import { useAuth } from '../contexts/useAuth';

// ---------- Constantes ----------

const ROLE_COLORS: Record<string, 'info' | 'warning' | 'default'> = {
  admin: 'info',
  manager: 'warning',
  sales: 'default',
};

const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  USER_ROLES.map((r) => [r.value, r.label]),
);

const USER_FILTERS: FilterDef[] = [
  {
    key: 'role',
    label: 'Rôle',
    type: 'select',
    options: USER_ROLES.map((r) => ({ value: r.value, label: r.label })),
  },
  {
    key: 'is_active',
    label: 'Statut',
    type: 'select',
    options: [
      { value: 'true', label: 'Actif' },
      { value: 'false', label: 'Inactif' },
    ],
  },
];

// ---------- Composant ----------

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});

  // Dialogue de confirmation
  const [confirmAction, setConfirmAction] = useState<{
    type: 'role' | 'active';
    userId: string;
    userName: string;
    value: string | boolean;
  } | null>(null);

  // Ajout d'un membre (dans l'org courante)
  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState({ email: '', full_name: '', password: '', role: 'sales' });
  const [addError, setAddError] = useState<string | null>(null);

  // ---------- Query ----------

  const { data, isLoading } = useQuery<PaginatedResponse<User>>({
    queryKey: ['admin-users', page, search, filters],
    queryFn: () =>
      getUsers({
        page,
        size: 25,
        ...(search ? { search } : {}),
        ...filters,
      }),
  });

  // ---------- Mutations ----------

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => updateUserRole(id, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setConfirmAction(null);
    },
  });

  const activeMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      toggleUserActive(id, is_active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setConfirmAction(null);
    },
  });

  const createMutation = useMutation({
    mutationFn: () => createUser(addForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setShowAdd(false);
      setAddForm({ email: '', full_name: '', password: '', role: 'sales' });
      setAddError(null);
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setAddError(typeof detail === 'string' ? detail : 'Echec de la creation du membre.');
    },
  });

  // ---------- Handlers ----------

  const handleRoleChange = (userId: string, userName: string, newRole: string) => {
    setConfirmAction({ type: 'role', userId, userName, value: newRole });
  };

  const handleToggleActive = (userId: string, userName: string, currentlyActive: boolean) => {
    setConfirmAction({ type: 'active', userId, userName, value: !currentlyActive });
  };

  const handleConfirm = () => {
    if (!confirmAction) return;
    if (confirmAction.type === 'role') {
      roleMutation.mutate({ id: confirmAction.userId, role: confirmAction.value as string });
    } else {
      activeMutation.mutate({ id: confirmAction.userId, is_active: confirmAction.value as boolean });
    }
  };

  // ---------- Rendu ----------

  return (
    <div className="p-8">
      {/* En-tete */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-50 rounded-lg flex items-center justify-center">
            <Shield className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Utilisateurs</h1>
            <p className="text-sm text-slate-400">Gestion des comptes et des rôles</p>
          </div>
        </div>
        <Button variant="primary" size="sm" icon={Plus} onClick={() => setShowAdd(true)}>
          Ajouter un membre
        </Button>
      </div>

      {/* Recherche + Filtres */}
      <div className="flex items-center gap-4 mb-4">
        <div className="w-80">
          <SearchInput
            value={search}
            onChange={(v: string) => {
              setSearch(v);
              setPage(1);
            }}
            placeholder="Rechercher par nom ou email..."
          />
        </div>
        <FilterBar
          filters={USER_FILTERS}
          values={filters}
          onChange={(key: string, value: string) => {
            setFilters((prev) => {
              const next = { ...prev };
              if (value) next[key] = value;
              else delete next[key];
              return next;
            });
            setPage(1);
          }}
          onReset={() => {
            setFilters({});
            setPage(1);
          }}
        />
      </div>

      {/* Table */}
      {isLoading ? (
        <LoadingSpinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={Users}
          message="Aucun utilisateur ne correspond aux critères."
        />
      ) : (
        <>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                    Utilisateur
                  </th>
                  <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                    Rôle
                  </th>
                  <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                    Statut
                  </th>
                  <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                    Date d'inscription
                  </th>
                  <th className="text-right text-xs font-medium text-slate-400 uppercase tracking-wider px-6 py-3">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {data.items.map((u) => {
                  const isSelf = u.id === currentUser?.id;
                  return (
                    <tr key={u.id} className="hover:bg-slate-25 transition-colors">
                      {/* Nom + email */}
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-slate-700">{u.full_name}</p>
                        <p className="text-xs text-slate-400">{u.email}</p>
                      </td>

                      {/* Role — select inline */}
                      <td className="px-6 py-4">
                        {isSelf ? (
                          <Badge variant={ROLE_COLORS[u.role] ?? 'default'}>
                            {ROLE_LABELS[u.role] ?? u.role}
                          </Badge>
                        ) : (
                          <select
                            value={u.role}
                            onChange={(e) => handleRoleChange(u.id, u.full_name, e.target.value)}
                            className="w-40 px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                          >
                            {USER_ROLES.map((r) => (
                              <option key={r.value} value={r.value}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>

                      {/* Statut actif */}
                      <td className="px-6 py-4">
                        <Badge variant={u.is_active ? 'success' : 'danger'}>
                          {u.is_active ? 'Actif' : 'Inactif'}
                        </Badge>
                      </td>

                      {/* Date */}
                      <td className="px-6 py-4 text-sm text-slate-500">
                        {u.created_at
                          ? new Date(u.created_at).toLocaleDateString('fr-FR')
                          : '—'}
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 text-right">
                        {!isSelf && (
                          <button
                            onClick={() => handleToggleActive(u.id, u.full_name, u.is_active)}
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                              u.is_active
                                ? 'text-red-600 hover:bg-red-50'
                                : 'text-emerald-600 hover:bg-emerald-50'
                            }`}
                          >
                            {u.is_active ? (
                              <>
                                <UserX className="w-3.5 h-3.5" />
                                Désactiver
                              </>
                            ) : (
                              <>
                                <UserCheck className="w-3.5 h-3.5" />
                                Activer
                              </>
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="mt-4">
              <Pagination page={page} pages={data.pages} total={data.total} onPageChange={setPage} />
            </div>
          )}
        </>
      )}

      {/* Modale : ajouter un membre */}
      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Ajouter un membre">
        <div className="space-y-4">
          {addError && (
            <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-2.5">
              {addError}
            </div>
          )}
          <Input
            label="Nom complet"
            value={addForm.full_name}
            onChange={(e) => setAddForm((f) => ({ ...f, full_name: e.target.value }))}
            placeholder="Jean Dupont"
          />
          <Input
            label="Email"
            type="email"
            value={addForm.email}
            onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
            placeholder="jean@entreprise.com"
          />
          <Input
            label="Mot de passe temporaire"
            type="password"
            value={addForm.password}
            onChange={(e) => setAddForm((f) => ({ ...f, password: e.target.value }))}
            helperText="8 caractères minimum. Le membre pourra le changer dans ses paramètres."
          />
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">Rôle</label>
            <select
              value={addForm.role}
              onChange={(e) => setAddForm((f) => ({ ...f, role: e.target.value }))}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              {USER_ROLES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowAdd(false)}>Annuler</Button>
            <Button
              variant="primary"
              loading={createMutation.isPending}
              disabled={!addForm.email || !addForm.full_name || addForm.password.length < 8}
              onClick={() => createMutation.mutate()}
            >
              Créer le membre
            </Button>
          </div>
        </div>
      </Modal>

      {/* Dialogue de confirmation */}
      <ConfirmDialog
        open={confirmAction !== null}
        onClose={() => setConfirmAction(null)}
        onConfirm={handleConfirm}
        title={
          confirmAction?.type === 'role'
            ? 'Changer le rôle'
            : confirmAction?.value
              ? 'Activer l\'utilisateur'
              : 'Désactiver l\'utilisateur'
        }
        message={
          confirmAction?.type === 'role'
            ? `Voulez-vous changer le rôle de ${confirmAction.userName} en "${ROLE_LABELS[confirmAction.value as string] ?? confirmAction.value}" ?`
            : confirmAction?.value
              ? `Voulez-vous réactiver le compte de ${confirmAction?.userName} ?`
              : `Voulez-vous désactiver le compte de ${confirmAction?.userName} ? L'utilisateur ne pourra plus se connecter.`
        }
        confirmLabel="Confirmer"
        loading={roleMutation.isPending || activeMutation.isPending}
      />
    </div>
  );
}
