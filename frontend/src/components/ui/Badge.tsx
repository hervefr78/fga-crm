// =============================================================================
// FGA CRM - Composant Badge reutilisable
// =============================================================================

import clsx from 'clsx';

const VARIANT_CLASSES = {
  default: 'bg-slate-100 text-slate-600',
  success: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-700',
  danger: 'bg-red-50 text-red-600',
  info: 'bg-blue-50 text-blue-700',
} as const;

interface BadgeProps {
  children: React.ReactNode;
  variant?: keyof typeof VARIANT_CLASSES;
  className?: string;
}

export default function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span className={clsx('px-2.5 py-1 text-xs font-medium rounded-full', VARIANT_CLASSES[variant], className)}>
      {children}
    </span>
  );
}
