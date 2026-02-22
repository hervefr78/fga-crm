// =============================================================================
// FGA CRM - Tests du composant Badge
// =============================================================================

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Badge from './Badge';

describe('Badge', () => {
  it('affiche le texte enfant', () => {
    render(<Badge>Email</Badge>);
    expect(screen.getByText('Email')).toBeInTheDocument();
  });

  it('applique la variante default', () => {
    render(<Badge variant="default">Default</Badge>);
    const el = screen.getByText('Default');
    expect(el.className).toContain('bg-slate-100');
  });

  it('applique la variante success', () => {
    render(<Badge variant="success">Actif</Badge>);
    const el = screen.getByText('Actif');
    expect(el.className).toContain('bg-emerald-50');
  });

  it('applique la variante warning', () => {
    render(<Badge variant="warning">En cours</Badge>);
    const el = screen.getByText('En cours');
    expect(el.className).toContain('bg-amber-50');
  });

  it('applique la variante danger', () => {
    render(<Badge variant="danger">Erreur</Badge>);
    const el = screen.getByText('Erreur');
    expect(el.className).toContain('bg-red-50');
  });

  it('applique la variante info', () => {
    render(<Badge variant="info">Info</Badge>);
    const el = screen.getByText('Info');
    expect(el.className).toContain('bg-blue-50');
  });

  it('accepte un className custom', () => {
    render(<Badge className="ml-2">Custom</Badge>);
    const el = screen.getByText('Custom');
    expect(el.className).toContain('ml-2');
  });
});
