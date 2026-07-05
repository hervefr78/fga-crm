// =============================================================================
// FGA CRM - Tests CompanyContactsEnrichBar (CTA enrichissement, contacts existants)
// =============================================================================

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { CompanyContactsEnrichBar } from './CompanyContactsEnrichBar';

const baseProps = {
  noEmailCount: 0,
  isEnriching: false,
  lastStatus: null,
  lastEmailsFound: null,
  quotaExceeded: false,
  sirenNotFound: false,
  isError: false,
  onEnrich: vi.fn(),
};

describe('CompanyContactsEnrichBar', () => {
  it('emails manquants : compte au pluriel + bouton "Chercher les emails manquants"', () => {
    render(<CompanyContactsEnrichBar {...baseProps} noEmailCount={3} />);
    expect(screen.getByText(/3 contacts sans email/i)).toBeInTheDocument();
    expect(screen.getByText(/Chercher les emails manquants/i)).toBeInTheDocument();
  });

  it('un seul email manquant : compte au singulier', () => {
    render(<CompanyContactsEnrichBar {...baseProps} noEmailCount={1} />);
    expect(screen.getByText(/1 contact sans email/i)).toBeInTheDocument();
    // pas de "contacts" au pluriel
    expect(screen.queryByText(/1 contacts sans email/i)).not.toBeInTheDocument();
  });

  it('aucun email manquant : propose de chercher d\'autres decideurs', () => {
    render(<CompanyContactsEnrichBar {...baseProps} noEmailCount={0} />);
    expect(screen.getByText(/Rechercher d'autres decideurs/i)).toBeInTheDocument();
    expect(screen.getByText(/Enrichir les decideurs/i)).toBeInTheDocument();
  });

  it('declenche onEnrich au clic', () => {
    const onEnrich = vi.fn();
    render(<CompanyContactsEnrichBar {...baseProps} noEmailCount={2} onEnrich={onEnrich} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onEnrich).toHaveBeenCalledTimes(1);
  });

  it('en cours : label "Recherche en cours..." et bouton desactive', () => {
    render(<CompanyContactsEnrichBar {...baseProps} isEnriching />);
    expect(screen.getByText(/Recherche en cours/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('quota depasse : message dedie', () => {
    render(<CompanyContactsEnrichBar {...baseProps} quotaExceeded />);
    expect(screen.getByText(/Quota journalier/i)).toBeInTheDocument();
  });

  it('SIREN introuvable : message d\'explication', () => {
    render(<CompanyContactsEnrichBar {...baseProps} sirenNotFound />);
    expect(screen.getByText(/SIREN introuvable/i)).toBeInTheDocument();
  });

  it('echec du job : message d\'echec', () => {
    render(<CompanyContactsEnrichBar {...baseProps} lastStatus="failed" />);
    expect(screen.getByText(/a echoue/i)).toBeInTheDocument();
  });

  it('job termine sans email manquant : message "liste a jour"', () => {
    render(<CompanyContactsEnrichBar {...baseProps} lastStatus="done" />);
    expect(screen.getByText(/liste est a jour/i)).toBeInTheDocument();
  });

  it('job termine + emails manquants restants + 0 trouve : "Aucun nouvel email trouve"', () => {
    render(
      <CompanyContactsEnrichBar
        {...baseProps}
        noEmailCount={3}
        lastStatus="done"
        lastEmailsFound={0}
      />,
    );
    expect(screen.getByText(/Aucun nouvel email trouve/i)).toBeInTheDocument();
  });

  it('job termine avec emails trouves : compte au pluriel', () => {
    render(<CompanyContactsEnrichBar {...baseProps} lastStatus="done" lastEmailsFound={2} />);
    expect(screen.getByText(/2 emails ajoutes/i)).toBeInTheDocument();
  });

  it('job termine avec 1 email trouve : compte au singulier', () => {
    render(<CompanyContactsEnrichBar {...baseProps} lastStatus="done" lastEmailsFound={1} />);
    expect(screen.getByText(/1 email ajoute/i)).toBeInTheDocument();
    expect(screen.queryByText(/1 emails ajoutes/i)).not.toBeInTheDocument();
  });
});
