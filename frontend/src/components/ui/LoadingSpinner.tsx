// =============================================================================
// FGA CRM - Composant LoadingSpinner reutilisable
// =============================================================================

import { RefreshCw } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
}

export default function LoadingSpinner({ message = 'Chargement...' }: LoadingSpinnerProps) {
  return (
    <div className="p-8 text-center text-slate-400">
      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
