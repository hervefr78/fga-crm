// =============================================================================
// FGA CRM - Tests CompanyContactsEmpty (CTA recherche de decideurs)
// =============================================================================

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { CompanyContactsEmpty } from './CompanyContactsEmpty';

const baseProps = {
  hasSiren: true,
  isEnriching: false,
  lastStatus: null,
  quotaExceeded: false,
  isError: false,
  onEnrich: vi.fn(),
};

describe('CompanyContactsEmpty', () => {
  it('affiche le bouton de recherche quand la societe a un SIREN', () => {
    render(<CompanyContactsEmpty {...baseProps} />);
    expect(screen.getByText(/Chercher les decideurs/i)).toBeInTheDocument();
  });

  it('declenche onEnrich au clic', () => {
    const onEnrich = vi.fn();
    render(<CompanyContactsEmpty {...baseProps} onEnrich={onEnrich} />);
    fireEvent.click(screen.getByText(/Chercher les decideurs/i));
    expect(onEnrich).toHaveBeenCalledTimes(1);
  });

  it('sans SIREN : pas de bouton, message d\'explication', () => {
    render(<CompanyContactsEmpty {...baseProps} hasSiren={false} />);
    expect(screen.queryByText(/Chercher les decideurs/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Renseignez le SIREN/i)).toBeInTheDocument();
  });

  it('en cours : label "Recherche..." et bouton desactive', () => {
    render(<CompanyContactsEmpty {...baseProps} isEnriching />);
    expect(screen.getByText(/Recherche des decideurs/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('quota depasse : message dedie', () => {
    render(<CompanyContactsEmpty {...baseProps} quotaExceeded />);
    expect(screen.getByText(/Quota journalier/i)).toBeInTheDocument();
  });

  it('job termine sans resultat : "Aucun decideur trouve"', () => {
    render(<CompanyContactsEmpty {...baseProps} lastStatus="done" />);
    expect(screen.getByText(/Aucun decideur trouve/i)).toBeInTheDocument();
  });

  it('echec du job : message d\'echec', () => {
    render(<CompanyContactsEmpty {...baseProps} lastStatus="failed" />);
    expect(screen.getByText(/a echoue/i)).toBeInTheDocument();
  });
});
