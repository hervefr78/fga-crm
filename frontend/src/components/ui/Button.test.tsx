// =============================================================================
// FGA CRM - Tests du composant Button
// =============================================================================

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Plus } from 'lucide-react';
import Button from './Button';

describe('Button', () => {
  it('affiche le texte enfant', () => {
    render(<Button>Nouveau contact</Button>);
    expect(screen.getByText('Nouveau contact')).toBeInTheDocument();
  });

  it('appelle onClick au clic', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Cliquer</Button>);
    fireEvent.click(screen.getByText('Cliquer'));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it('est desactive quand disabled=true', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByText('Disabled').closest('button')).toBeDisabled();
  });

  it('est desactive quand loading=true', () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByText('Loading').closest('button')).toBeDisabled();
  });

  it('applique la variante primary par defaut', () => {
    render(<Button>Primary</Button>);
    const btn = screen.getByText('Primary').closest('button');
    expect(btn?.className).toContain('bg-primary-600');
  });

  it('applique la variante secondary', () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByText('Secondary').closest('button');
    expect(btn?.className).toContain('border-slate-200');
  });

  it('applique la variante danger', () => {
    render(<Button variant="danger">Danger</Button>);
    const btn = screen.getByText('Danger').closest('button');
    expect(btn?.className).toContain('bg-red-600');
  });

  it('affiche une icone si fournie', () => {
    render(<Button icon={Plus}>Avec icone</Button>);
    // L'icone lucide genere un SVG
    const btn = screen.getByText('Avec icone').closest('button');
    expect(btn?.querySelector('svg')).toBeTruthy();
  });
});
