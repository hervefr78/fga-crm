// =============================================================================
// FGA CRM - Composant Button reutilisable
// =============================================================================

import { forwardRef } from 'react';
import { RefreshCw } from 'lucide-react';
import clsx from 'clsx';

const VARIANT_CLASSES = {
  primary: 'bg-primary-600 hover:bg-primary-700 text-white',
  secondary: 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50',
  danger: 'bg-red-600 hover:bg-red-700 text-white',
  ghost: 'text-slate-500 hover:bg-slate-50 hover:text-slate-700',
} as const;

const SIZE_CLASSES = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2.5 text-sm',
} as const;

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof VARIANT_CLASSES;
  size?: keyof typeof SIZE_CLASSES;
  loading?: boolean;
  icon?: React.ElementType;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading = false, icon: Icon, className, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={clsx(
          'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-colors disabled:opacity-50',
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          className,
        )}
        {...props}
      >
        {loading ? (
          <RefreshCw className="w-4 h-4 animate-spin" />
        ) : Icon ? (
          <Icon className="w-4 h-4" />
        ) : null}
        {children}
      </button>
    );
  },
);

Button.displayName = 'Button';
export default Button;
