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
