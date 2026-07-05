// =============================================================================
// FGA CRM - Tests CompanyContactsEmpty (CTA recherche de decideurs)
// =============================================================================

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { CompanyContactsEmpty } from './CompanyContactsEmpty';

const baseProps = {
  isEnriching: false,
  lastStatus: null,
  quotaExceeded: false,
  sirenNotFound: false,
  isError: false,
  onEnrich: vi.fn(),
};

describe('CompanyContactsEmpty', () => {
  it('affiche toujours le bouton de recherche', () => {
    render(<CompanyContactsEmpty {...baseProps} />);
    expect(screen.getByText(/Chercher les decideurs/i)).toBeInTheDocument();
  });

  it('declenche onEnrich au clic', () => {
    const onEnrich = vi.fn();
    render(<CompanyContactsEmpty {...baseProps} onEnrich={onEnrich} />);
    fireEvent.click(screen.getByText(/Chercher les decideurs/i));
    expect(onEnrich).toHaveBeenCalledTimes(1);
  });

  it('SIREN introuvable : message d\'explication, bouton toujours la (retry)', () => {
    render(<CompanyContactsEmpty {...baseProps} sirenNotFound />);
    expect(screen.getByText(/SIREN introuvable/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeInTheDocument();
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
