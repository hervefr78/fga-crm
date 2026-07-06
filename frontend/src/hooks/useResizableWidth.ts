// =============================================================================
// FGA CRM - Hook : largeur de panneau redimensionnable (drag + persistance)
// =============================================================================
// Rend un panneau lateral redimensionnable a la souris. La largeur est bornee
// (min/max) et persistee en localStorage (par cle) — restauree au chargement.
// Utilise par la sidebar de navigation et la colonne liste (split-view).
// =============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';

interface UseResizableWidthOptions {
  storageKey: string;
  defaultWidth: number;
  min: number;
  max: number;
}

interface UseResizableWidthResult {
  width: number;
  startResize: (e: React.MouseEvent) => void;
  isResizing: boolean;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function readStored(storageKey: string, defaultWidth: number, min: number, max: number): number {
  try {
    const raw = localStorage.getItem(storageKey);
    const parsed = raw !== null ? Number(raw) : NaN;
    return Number.isFinite(parsed) ? clamp(parsed, min, max) : defaultWidth;
  } catch {
    return defaultWidth; // localStorage indispo (mode prive strict)
  }
}

export function useResizableWidth({
  storageKey, defaultWidth, min, max,
}: UseResizableWidthOptions): UseResizableWidthResult {
  const [width, setWidth] = useState<number>(() =>
    readStored(storageKey, defaultWidth, min, max),
  );
  const [isResizing, setIsResizing] = useState(false);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startWidth: width };
    setIsResizing(true);
  }, [width]);

  // Drag actif : suit la souris (window) + garde-fous UX (pas de selection de texte).
  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      setWidth(clamp(drag.startWidth + (e.clientX - drag.startX), min, max));
    };
    const onUp = () => {
      setIsResizing(false);
      dragRef.current = null;
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    const prevUserSelect = document.body.style.userSelect;
    const prevCursor = document.body.style.cursor;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.userSelect = prevUserSelect;
      document.body.style.cursor = prevCursor;
    };
  }, [isResizing, min, max]);

  // Persiste la largeur en fin de drag (pas a chaque mousemove).
  useEffect(() => {
    if (isResizing) return;
    try {
      localStorage.setItem(storageKey, String(width));
    } catch {
      // localStorage indispo : la largeur reste en memoire pour la session.
    }
  }, [isResizing, width, storageKey]);

  return { width, startResize, isResizing };
}
