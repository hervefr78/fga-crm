// =============================================================================
// FGA CRM - Vitest Setup (jsdom + Testing Library matchers)
// =============================================================================

import '@testing-library/jest-dom';

// jsdom n'implemente pas ResizeObserver, requis par recharts ResponsiveContainer.
// Polyfill minimal (no-op) — centralise ici pour tous les tests (DC8).
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as unknown as typeof ResizeObserver);

// jsdom peut ne pas fournir un localStorage complet : stub Map-backed (DC8).
if (typeof globalThis.localStorage === 'undefined'
  || typeof globalThis.localStorage.clear !== 'function') {
  const store = new Map<string, string>();
  const mock: Storage = {
    get length() { return store.size; },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    removeItem: (k: string) => { store.delete(k); },
    setItem: (k: string, v: string) => { store.set(k, String(v)); },
  };
  Object.defineProperty(globalThis, 'localStorage', {
    value: mock, configurable: true, writable: true,
  });
}
