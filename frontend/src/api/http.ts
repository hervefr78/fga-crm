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

// Faut-il forcer un rechargement vers /login sur cette reponse ?
// Garde anti-boucle : NE PAS rediriger si on est deja sur /login. Sinon la sonde
// `getMe()` du boot (AuthContext, sans token) recoit un 401 -> window.location
// reload -> re-sonde -> 401 -> reload... = clignotement infini. Sur /login, on
// laisse l'erreur remonter : AuthContext.catch affiche le formulaire.
export function shouldForceLoginRedirect(
  status: number | undefined,
  token: string | null,
  pathname: string,
): boolean {
  return status === 401 && token !== 'dev-bypass' && !pathname.startsWith('/login');
}

// Handle 401 globally (sauf en mode bypass)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      shouldForceLoginRedirect(
        error.response?.status,
        localStorage.getItem('access_token'),
        window.location.pathname,
      )
    ) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default api;
