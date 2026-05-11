// =============================================================================
// FGA CRM - Tests LinkedinIndicator (Phase B 2026-05)
// =============================================================================

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LinkedinIndicator from './LinkedinIndicator';

describe('LinkedinIndicator', () => {
  it('affiche "Vérifié" pour status=verified', () => {
    render(<LinkedinIndicator status="verified" />);
    expect(screen.getByText('Vérifié')).toBeInTheDocument();
  });

  it('affiche "À vérifier" pour status=candidate (URL générée)', () => {
    render(<LinkedinIndicator status="candidate" />);
    expect(screen.getByText('À vérifier')).toBeInTheDocument();
  });

  it('expose un tooltip explicatif pour status=candidate', () => {
    render(<LinkedinIndicator status="candidate" />);
    const wrapper = screen.getByText('À vérifier').closest('span[title]');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.getAttribute('title')).toContain('générée');
  });

  it('affiche "Invalide" pour status=invalid', () => {
    render(<LinkedinIndicator status="invalid" />);
    expect(screen.getByText('Invalide')).toBeInTheDocument();
  });

  it('ne rend rien si status est null', () => {
    const { container } = render(<LinkedinIndicator status={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('ne rend rien si status est undefined', () => {
    const { container } = render(<LinkedinIndicator status={undefined} />);
    expect(container.firstChild).toBeNull();
  });
});
