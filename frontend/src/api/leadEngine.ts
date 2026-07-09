// =============================================================================
// FGA CRM - API Lead Engine (Signal Inbox)
// =============================================================================
// Aligne sur app/api/v1/lead_engine.py. Instance `api` partagee (JWT injecte).
// =============================================================================

import api from './http';
import type {
  LeadScanResult, LeadSignal, LeadSignalList, LeadSignalStatus,
  LeadSignalType, LeadSignalUpdateInput,
} from '../types/leadEngine';

export const listLeadSignals = async (params: {
  status?: LeadSignalStatus;
  signal_type?: LeadSignalType;
  page?: number;
  size?: number;
}): Promise<LeadSignalList> => {
  const r = await api.get('/lead-engine/signals', { params });
  return r.data as LeadSignalList;
};

export const updateLeadSignal = async (
  signalId: string,
  payload: LeadSignalUpdateInput,
): Promise<LeadSignal> => {
  const r = await api.patch(`/lead-engine/signals/${signalId}`, payload);
  return r.data as LeadSignal;
};

export const runLeadScan = async (): Promise<LeadScanResult> => {
  const r = await api.post('/lead-engine/scan');
  return r.data as LeadScanResult;
};
