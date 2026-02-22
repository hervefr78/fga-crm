// =============================================================================
// FGA CRM - API Client
// =============================================================================

import axios from 'axios';
import api, { API_ROOT } from './http';

// ---------- Health ----------
export const getHealth = async () => {
  const response = await axios.get(`${API_ROOT.replace('/api/v1', '')}/health`);
  return response.data;
};

// ---------- Auth ----------
export const login = async (email: string, password: string) => {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);
  const response = await api.post('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
};

export const register = async (email: string, password: string, full_name: string) => {
  const response = await api.post('/auth/register', { email, password, full_name });
  return response.data;
};

export const getMe = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

export const updateProfile = async (data: { full_name?: string; avatar_url?: string }) => {
  const response = await api.put('/auth/me', data);
  return response.data;
};

export const changePassword = async (currentPassword: string, newPassword: string) => {
  const response = await api.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return response.data;
};

// ---------- Contacts ----------
export const getContacts = async (params?: Record<string, unknown>) => {
  const response = await api.get('/contacts', { params });
  return response.data;
};

export const getContact = async (id: string) => {
  const response = await api.get(`/contacts/${id}`);
  return response.data;
};

export const createContact = async (data: Record<string, unknown>) => {
  const response = await api.post('/contacts', data);
  return response.data;
};

export const updateContact = async (id: string, data: Record<string, unknown>) => {
  const response = await api.put(`/contacts/${id}`, data);
  return response.data;
};

export const deleteContact = async (id: string) => {
  await api.delete(`/contacts/${id}`);
};

// ---------- Companies ----------
export const getCompanies = async (params?: Record<string, unknown>) => {
  const response = await api.get('/companies', { params });
  return response.data;
};

export const getCompany = async (id: string) => {
  const response = await api.get(`/companies/${id}`);
  return response.data;
};

export const createCompany = async (data: Record<string, unknown>) => {
  const response = await api.post('/companies', data);
  return response.data;
};

export const updateCompany = async (id: string, data: Record<string, unknown>) => {
  const response = await api.put(`/companies/${id}`, data);
  return response.data;
};

export const deleteCompany = async (id: string) => {
  await api.delete(`/companies/${id}`);
};

// ---------- Deals ----------
export const getDeals = async (params?: Record<string, unknown>) => {
  const response = await api.get('/deals', { params });
  return response.data;
};

export const getDeal = async (id: string) => {
  const response = await api.get(`/deals/${id}`);
  return response.data;
};

export const createDeal = async (data: Record<string, unknown>) => {
  const response = await api.post('/deals', data);
  return response.data;
};

export const updateDeal = async (id: string, data: Record<string, unknown>) => {
  const response = await api.put(`/deals/${id}`, data);
  return response.data;
};

export const updateDealStage = async (id: string, stage: string) => {
  const response = await api.patch(`/deals/${id}/stage`, { stage });
  return response.data;
};

export const deleteDeal = async (id: string) => {
  await api.delete(`/deals/${id}`);
};

// ---------- Tasks ----------
export const getTasks = async (params?: Record<string, unknown>) => {
  const response = await api.get('/tasks', { params });
  return response.data;
};

export const getTask = async (id: string) => {
  const response = await api.get(`/tasks/${id}`);
  return response.data;
};

export const createTask = async (data: Record<string, unknown>) => {
  const response = await api.post('/tasks', data);
  return response.data;
};

export const updateTask = async (id: string, data: Record<string, unknown>) => {
  const response = await api.put(`/tasks/${id}`, data);
  return response.data;
};

export const toggleTaskCompletion = async (id: string, is_completed: boolean) => {
  const response = await api.patch(`/tasks/${id}/complete`, { is_completed });
  return response.data;
};

export const deleteTask = async (id: string) => {
  await api.delete(`/tasks/${id}`);
};

// ---------- Activities ----------
export const getActivities = async (params?: Record<string, unknown>) => {
  const response = await api.get('/activities', { params });
  return response.data;
};

export const getActivity = async (id: string) => {
  const response = await api.get(`/activities/${id}`);
  return response.data;
};

export const createActivity = async (data: Record<string, unknown>) => {
  const response = await api.post('/activities', data);
  return response.data;
};

export const updateActivity = async (id: string, data: Record<string, unknown>) => {
  const response = await api.put(`/activities/${id}`, data);
  return response.data;
};

export const deleteActivity = async (id: string) => {
  await api.delete(`/activities/${id}`);
};

// ---------- Import CSV ----------
export const importContacts = async (rows: Record<string, unknown>[]) => {
  const response = await api.post('/contacts/import', { rows });
  return response.data;
};

export const importCompanies = async (rows: Record<string, unknown>[]) => {
  const response = await api.post('/companies/import', { rows });
  return response.data;
};

// ---------- Admin — User Management ----------
export const getUsers = async (params?: Record<string, unknown>) => {
  const response = await api.get('/users', { params });
  return response.data;
};

export const getUser = async (id: string) => {
  const response = await api.get(`/users/${id}`);
  return response.data;
};

export const updateUserRole = async (id: string, role: string) => {
  const response = await api.patch(`/users/${id}/role`, { role });
  return response.data;
};

export const toggleUserActive = async (id: string, is_active: boolean) => {
  const response = await api.patch(`/users/${id}/deactivate`, { is_active });
  return response.data;
};

// ---------- Emails ----------
export const sendEmail = async (data: Record<string, unknown>) => {
  const response = await api.post('/emails/send', data);
  return response.data;
};

export const getEmails = async (params?: Record<string, unknown>) => {
  const response = await api.get('/emails', { params });
  return response.data;
};

// ---------- Email Templates ----------
export const getEmailTemplates = async (params?: Record<string, unknown>) => {
  const response = await api.get('/email-templates', { params });
  return response.data;
};

export const getEmailTemplate = async (id: string) => {
  const response = await api.get(`/email-templates/${id}`);
  return response.data;
};

export const createEmailTemplate = async (data: Record<string, unknown>) => {
  const response = await api.post('/email-templates', data);
  return response.data;
};

export const updateEmailTemplate = async (id: string, data: Record<string, unknown>) => {
  const response = await api.put(`/email-templates/${id}`, data);
  return response.data;
};

export const deleteEmailTemplate = async (id: string) => {
  await api.delete(`/email-templates/${id}`);
};

// ---------- Integrations (Startup Radar) ----------
export const syncStartupRadar = async () => {
  const response = await api.post('/integrations/startup-radar/sync');
  return response.data;
};

export const getSyncStatus = async () => {
  const response = await api.get('/integrations/startup-radar/status');
  return response.data;
};

export const triggerCompanyAudit = async (companyId: string) => {
  const response = await api.post(`/integrations/startup-radar/audit/${companyId}`);
  return response.data;
};

// ---------- Dashboard ----------
export const getDashboardStats = async () => {
  const response = await api.get('/dashboard/stats');
  return response.data;
};

// ---------- Recherche globale ----------
export const globalSearch = async (q: string) => {
  const response = await api.get('/search', { params: { q } });
  return response.data;
};
