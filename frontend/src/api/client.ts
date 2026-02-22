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

export const deleteCompany = async (id: string) => {
  await api.delete(`/companies/${id}`);
};

// ---------- Deals ----------
export const getDeals = async (params?: Record<string, unknown>) => {
  const response = await api.get('/deals', { params });
  return response.data;
};

export const createDeal = async (data: Record<string, unknown>) => {
  const response = await api.post('/deals', data);
  return response.data;
};

export const updateDealStage = async (id: string, stage: string) => {
  const response = await api.patch(`/deals/${id}/stage`, null, { params: { stage } });
  return response.data;
};
