// =============================================================================
// FGA CRM - API Enrichissement (feature Compass)
// =============================================================================
// Aligne sur app/api/v1/enrichment.py. Instance `api` partagee (JWT injecte).
// =============================================================================

import api from './http';
import type {
  EnrichmentJob, EnrichmentJobCreateInput, EnrichmentJobList,
} from '../types/enrichment';

export const createEnrichmentJob = async (
  payload: EnrichmentJobCreateInput,
): Promise<EnrichmentJob> => {
  const r = await api.post('/enrichment/jobs', payload);
  return r.data as EnrichmentJob;
};

export const listEnrichmentJobs = async (
  page = 1,
  size = 20,
): Promise<EnrichmentJobList> => {
  const r = await api.get('/enrichment/jobs', { params: { page, size } });
  return r.data as EnrichmentJobList;
};

export const getEnrichmentJob = async (jobId: string): Promise<EnrichmentJob> => {
  const r = await api.get(`/enrichment/jobs/${jobId}`);
  return r.data as EnrichmentJob;
};

// Raccourci Mode A : enrichir les decideurs (CEO/CTO/CMO/CPO) d'une societe
// depuis sa fiche. Cree un job async (Celery) qui trouve les personnes via
// Icypeas, verifie les emails (RGPD) et ecrit les contacts lies a la societe.
export const enrichCompany = async (siren: string): Promise<EnrichmentJob> => {
  const r = await api.post(`/enrichment/companies/${encodeURIComponent(siren)}/enrich`);
  return r.data as EnrichmentJob;
};

// Variante par ID CRM : marche meme sans SIREN (le serveur le resout via l'annuaire
// officiel a partir du nom, ou renvoie 422 s'il n'y arrive pas).
export const enrichCompanyById = async (companyId: string): Promise<EnrichmentJob> => {
  const r = await api.post(`/enrichment/companies/by-id/${encodeURIComponent(companyId)}/enrich`);
  return r.data as EnrichmentJob;
};
