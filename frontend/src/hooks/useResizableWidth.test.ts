// =============================================================================
// FGA CRM - Tests useResizableWidth (largeur persistee + drag)
// =============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useResizableWidth } from './useResizableWidth';

const OPTS = { storageKey: 'test.width', defaultWidth: 300, min: 200, max: 500 };

function fakeMouseDown(clientX: number) {
  return { clientX, preventDefault: () => {} } as unknown as React.MouseEvent;
}

describe('useResizableWidth', () => {
  beforeEach(() => localStorage.clear());

  it('largeur par defaut sans valeur stockee', () => {
    const { result } = renderHook(() => useResizableWidth(OPTS));
    expect(result.current.width).toBe(300);
  });

  it('restaure la largeur stockee', () => {
    localStorage.setItem('test.width', '450');
    const { result } = renderHook(() => useResizableWidth(OPTS));
    expect(result.current.width).toBe(450);
  });

  it('borne la valeur stockee au max', () => {
    localStorage.setItem('test.width', '9999');
    const { result } = renderHook(() => useResizableWidth(OPTS));
    expect(result.current.width).toBe(500);
  });

  it('drag : met a jour la largeur puis persiste au relachement', () => {
    const { result } = renderHook(() => useResizableWidth(OPTS));

    act(() => result.current.startResize(fakeMouseDown(100)));
    expect(result.current.isResizing).toBe(true);

    act(() => { window.dispatchEvent(new MouseEvent('mousemove', { clientX: 180 })); });
    expect(result.current.width).toBe(380); // 300 + (180-100)

    act(() => { window.dispatchEvent(new MouseEvent('mouseup')); });
    expect(result.current.isResizing).toBe(false);
    expect(localStorage.getItem('test.width')).toBe('380');
  });

  it('drag : borne au min', () => {
    const { result } = renderHook(() => useResizableWidth(OPTS));
    act(() => result.current.startResize(fakeMouseDown(100)));
    act(() => { window.dispatchEvent(new MouseEvent('mousemove', { clientX: 0 })); });
    expect(result.current.width).toBe(200); // 300 - 100 = 200 (min)
  });
});
