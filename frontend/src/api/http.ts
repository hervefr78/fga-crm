// =============================================================================
// FGA CRM - HTTP Client
// =============================================================================

import axios from 'axios';

export const API_ROOT = import.meta.env.VITE_API_URL || 'http://localhost:8300/api/v1';

const api = axios.create({
  baseURL: API_ROOT,
});

// Inject JWT token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default api;
