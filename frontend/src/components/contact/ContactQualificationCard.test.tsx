// =============================================================================
// FGA CRM - Tests ContactQualificationCard (carte SPICED)
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import type { Contact } from '../../types';

vi.mock('../../api/client', () => ({
  qualifyContact: vi.fn(),
}));

import { qualifyContact } from '../../api/client';
import ContactQualificationCard from './ContactQualificationCard';

const baseContact = {
  id: 'c1', first_name: 'Lea', last_name: 'Inbound', full_name: 'Lea Inbound',
  email: null, email_status: null, phone: null, title: null, job_level: null,
  department: null, is_decision_maker: false, linkedin_url: null, status: 'lead',
  lead_score: 0, source: null, company_id: null, company_name: null,
  owner_id: null, owner_name: null, created_at: '2026-07-01', updated_at: null,
  updated_by_name: null, ai_qualification: null, ai_routing: null, ai_qualified_at: null,
} as Contact;

const qualifiedContact: Contact = {
  ...baseContact,
  ai_routing: 'human_review',
  ai_qualified_at: '2026-07-08T10:00:00Z',
  ai_qualification: {
    spiced: {
      situation: { value: 'startup B2B post-levee Serie A', source: 'fiche' },
      pain: { value: 'unknown', source: 'unknown' },
      impact: { value: 'unknown', source: 'unknown' },
      critical_event: { value: 'unknown', source: 'unknown' },
      decision: { value: 'CTO decisionnaire', source: 'titre' },
    },
    routing_rationale: 'Signaux contradictoires.',
    suggested_product: 'audit-999',
    next_action: 'Planifier une revue humaine.',
    model: 'gpt-4o-mini',
    prompt_version: 'qualif-v1',
  },
};

function renderCard(contact: Contact) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ContactQualificationCard contact={contact} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ContactQualificationCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('contact non qualifie : etat vide + bouton Qualifier', () => {
    renderCard(baseContact);
    expect(screen.getByText(/Pas encore qualifié/)).toBeInTheDocument();
    expect(screen.getByText('Qualifier')).toBeInTheDocument();
  });

  it('contact qualifie : routing, grille SPICED avec unknown, prochaine action', () => {
    renderCard(qualifiedContact);
    expect(screen.getByText('À revoir')).toBeInTheDocument();
    expect(screen.getByText(/startup B2B post-levee/)).toBeInTheDocument();
    expect(screen.getByText('CTO decisionnaire')).toBeInTheDocument();
    expect(screen.getAllByText('unknown')).toHaveLength(3);
    expect(screen.getByText('Planifier une revue humaine.')).toBeInTheDocument();
    expect(screen.getByText('Re-qualifier')).toBeInTheDocument();
  });

  it('clic Qualifier -> appelle qualifyContact', async () => {
    vi.mocked(qualifyContact).mockResolvedValue({ deal_created_id: null });
    renderCard(baseContact);
    fireEvent.click(screen.getByText('Qualifier'));
    await waitFor(() => expect(qualifyContact).toHaveBeenCalledWith('c1'));
  });

  it('fast_track : affiche le lien vers le deal cree', async () => {
    vi.mocked(qualifyContact).mockResolvedValue({ deal_created_id: 'd42' });
    renderCard(baseContact);
    fireEvent.click(screen.getByText('Qualifier'));
    expect(await screen.findByText(/Deal créé automatiquement/)).toBeInTheDocument();
    expect(screen.getByText('ouvrir le deal').closest('a')).toHaveAttribute(
      'href', '/pipeline/d42',
    );
  });

  it('echec : message d erreur', async () => {
    vi.mocked(qualifyContact).mockRejectedValue(new Error('502'));
    renderCard(baseContact);
    fireEvent.click(screen.getByText('Qualifier'));
    expect(await screen.findByText(/Qualification indisponible/)).toBeInTheDocument();
  });
});
