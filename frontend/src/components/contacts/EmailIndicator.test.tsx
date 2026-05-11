// =============================================================================
// FGA CRM - Tests EmailIndicator (Phase B 2026-05)
// =============================================================================

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import EmailIndicator from './EmailIndicator';

describe('EmailIndicator', () => {
  it('affiche "Vérifié" pour email_status=valid', () => {
    render(<EmailIndicator emailStatus="valid" />);
    expect(screen.getByText('Vérifié')).toBeInTheDocument();
  });

  it('affiche "Candidat" pour email_status=unknown (heuristique)', () => {
    render(<EmailIndicator emailStatus="unknown" emailPattern="first.last" />);
    expect(screen.getByText('Candidat')).toBeInTheDocument();
  });

  it('inclut le pattern dans le tooltip si fourni', () => {
    render(<EmailIndicator emailStatus="unknown" emailPattern="flast" />);
    const wrapper = screen.getByText('Candidat').closest('span[title]');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.getAttribute('title')).toContain('flast');
  });

  it('affiche "Risqué" pour email_status=risky', () => {
    render(<EmailIndicator emailStatus="risky" />);
    expect(screen.getByText('Risqué')).toBeInTheDocument();
  });

  it('affiche "Risqué" pour email_status=invalid (alias)', () => {
    render(<EmailIndicator emailStatus="invalid" />);
    expect(screen.getByText('Risqué')).toBeInTheDocument();
  });

  it('ne rend rien si emailStatus est null', () => {
    const { container } = render(<EmailIndicator emailStatus={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('ne rend rien si emailStatus est undefined', () => {
    const { container } = render(<EmailIndicator emailStatus={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('ne rend rien si emailStatus est une valeur inconnue', () => {
    const { container } = render(<EmailIndicator emailStatus="bogus" />);
    expect(container.firstChild).toBeNull();
  });
});
