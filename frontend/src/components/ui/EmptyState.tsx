// =============================================================================
// FGA CRM - Composant EmptyState reutilisable
// =============================================================================

interface EmptyStateProps {
  icon: React.ElementType;
  message: string;
  action?: React.ReactNode;
}

export default function EmptyState({ icon: Icon, message, action }: EmptyStateProps) {
  return (
    <div className="p-8 text-center text-slate-400">
      <Icon className="w-6 h-6 mx-auto mb-2" />
      <p className="text-sm">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
