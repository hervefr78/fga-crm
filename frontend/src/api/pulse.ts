// =============================================================================
// FGA CRM - API FGA Pulse (radar editorial LinkedIn)
// =============================================================================
// Pulse est un SERVICE AUTONOME (pulse.fast-growth.fr), pas le backend CRM. On
// utilise donc une instance axios dediee (base VITE_PULSE_API_URL), distincte de
// `./http`. Sprint 0 : seule la sonde /health est cablee (onglet en etat vide).
// =============================================================================

import axios from 'axios';

export const PULSE_API_ROOT =
  import.meta.env.VITE_PULSE_API_URL || 'http://localhost:8400';

const pulseApi = axios.create({ baseURL: PULSE_API_ROOT });

export interface PulseHealth {
  status: 'ok' | 'degraded';
  db: 'ok' | 'down';
  redis: 'ok' | 'down';
}

export const getPulseHealth = async (): Promise<PulseHealth> => {
  // /health renvoie 503 en mode degrade : on veut la payload, pas une exception.
  const r = await pulseApi.get('/health', {
    validateStatus: (s) => s === 200 || s === 503,
  });
  return r.data as PulseHealth;
};
