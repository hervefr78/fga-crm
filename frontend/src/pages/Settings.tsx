// =============================================================================
// FGA CRM - Page Parametres (profil + mot de passe)
// =============================================================================

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, Lock, Building2 } from 'lucide-react';

import { updateProfile, changePassword, getMyOrganization, renameOrganization } from '../api/client';
import { useAuth } from '../contexts/useAuth';
import { isAdmin, type Organization } from '../types';
import { Button, Input } from '../components/ui';

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();

  // --- Section Organisation ---
  const { data: org } = useQuery<Organization>({
    queryKey: ['my-org'],
    queryFn: getMyOrganization,
  });
  const [orgNameEdit, setOrgNameEdit] = useState<string | null>(null);
  const [orgMsg, setOrgMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const orgName = orgNameEdit ?? org?.name ?? '';
  const canEditOrg = isAdmin(user);

  const orgMutation = useMutation({
    mutationFn: () => renameOrganization(orgName.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-org'] });
      setOrgMsg({ type: 'success', text: 'Organisation mise a jour.' });
    },
    onError: () => setOrgMsg({ type: 'error', text: 'Erreur lors de la mise a jour.' }),
  });

  // --- Section Profil ---
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [profileMsg, setProfileMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const profileMutation = useMutation({
    mutationFn: () => updateProfile({ full_name: fullName }),
    onSuccess: async () => {
      await refreshUser();
      setProfileMsg({ type: 'success', text: 'Profil mis a jour.' });
    },
    onError: () => {
      setProfileMsg({ type: 'error', text: 'Erreur lors de la mise a jour.' });
    },
  });

  // --- Section Mot de passe ---
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMsg, setPasswordMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const passwordMutation = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordMsg({ type: 'success', text: 'Mot de passe modifie avec succes.' });
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { status?: number } };
      if (axiosError.response?.status === 400) {
        setPasswordMsg({ type: 'error', text: 'Mot de passe actuel incorrect.' });
      } else {
        setPasswordMsg({ type: 'error', text: 'Erreur lors du changement de mot de passe.' });
      }
    },
  });

  const handlePasswordSubmit = () => {
    setPasswordMsg(null);

    if (newPassword.length < 8) {
      setPasswordMsg({ type: 'error', text: 'Le nouveau mot de passe doit faire au moins 8 caracteres.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ type: 'error', text: 'Les mots de passe ne correspondent pas.' });
      return;
    }

    passwordMutation.mutate();
  };

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Parametres</h1>

      {/* Section Organisation */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Building2 className="w-5 h-5 text-slate-400" />
          <h2 className="text-lg font-semibold text-slate-700">Organisation</h2>
        </div>

        <div className="space-y-4">
          <Input
            label="Nom de l'organisation"
            value={orgName}
            disabled={!canEditOrg}
            readOnly={!canEditOrg}
            onChange={(e) => {
              setOrgNameEdit(e.target.value);
              setOrgMsg(null);
            }}
            helperText={canEditOrg ? undefined : 'Seul un administrateur peut renommer l’organisation.'}
          />

          {orgMsg && (
            <p className={`text-sm ${orgMsg.type === 'success' ? 'text-emerald-600' : 'text-red-500'}`}>
              {orgMsg.text}
            </p>
          )}

          {canEditOrg && (
            <Button
              icon={Save}
              onClick={() => {
                setOrgMsg(null);
                orgMutation.mutate();
              }}
              loading={orgMutation.isPending}
              disabled={!orgName.trim() || orgName === org?.name}
            >
              Enregistrer
            </Button>
          )}
        </div>
      </div>

      {/* Section Profil */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold text-slate-700 mb-4">Profil</h2>

        <div className="space-y-4">
          <Input
            label="Nom complet"
            value={fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              setProfileMsg(null);
            }}
            placeholder="Votre nom"
          />

          <Input
            label="Email"
            value={user?.email || ''}
            disabled
            readOnly
          />

          {profileMsg && (
            <p className={`text-sm ${profileMsg.type === 'success' ? 'text-emerald-600' : 'text-red-500'}`}>
              {profileMsg.text}
            </p>
          )}

          <Button
            icon={Save}
            onClick={() => {
              setProfileMsg(null);
              profileMutation.mutate();
            }}
            loading={profileMutation.isPending}
            disabled={!fullName.trim() || fullName === user?.full_name}
          >
            Enregistrer
          </Button>
        </div>
      </div>

      {/* Section Mot de passe */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-slate-700 mb-4">Mot de passe</h2>

        <div className="space-y-4">
          <Input
            label="Mot de passe actuel"
            type="password"
            value={currentPassword}
            onChange={(e) => {
              setCurrentPassword(e.target.value);
              setPasswordMsg(null);
            }}
            placeholder="••••••••"
          />

          <Input
            label="Nouveau mot de passe"
            type="password"
            value={newPassword}
            onChange={(e) => {
              setNewPassword(e.target.value);
              setPasswordMsg(null);
            }}
            placeholder="Minimum 8 caracteres"
          />

          <Input
            label="Confirmer le nouveau mot de passe"
            type="password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              setPasswordMsg(null);
            }}
            placeholder="••••••••"
          />

          {passwordMsg && (
            <p className={`text-sm ${passwordMsg.type === 'success' ? 'text-emerald-600' : 'text-red-500'}`}>
              {passwordMsg.text}
            </p>
          )}

          <Button
            icon={Lock}
            onClick={handlePasswordSubmit}
            loading={passwordMutation.isPending}
            disabled={!currentPassword || !newPassword || !confirmPassword}
          >
            Modifier le mot de passe
          </Button>
        </div>
      </div>
    </div>
  );
}
