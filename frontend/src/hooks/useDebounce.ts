// =============================================================================
// FGA CRM - Hook useDebounce
// =============================================================================

import { useEffect, useState } from 'react';

/**
 * Retourne une valeur debounced qui ne se met a jour
 * qu'apres `delay` ms sans changement de `value`.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
