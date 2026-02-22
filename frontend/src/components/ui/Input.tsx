// =============================================================================
// FGA CRM - Composant Input reutilisable
// =============================================================================

import { forwardRef, useId } from 'react';
import clsx from 'clsx';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className, ...props }, ref) => {
    const generatedId = useId();
    const inputId = props.id || generatedId;

    return (
      <div>
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-slate-600 mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={clsx(
            'w-full px-3.5 py-2.5 bg-slate-50 border rounded-lg text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:border-transparent transition-colors',
            error
              ? 'border-red-300 focus:ring-red-500'
              : 'border-slate-200 focus:ring-primary-500',
            className,
          )}
          {...props}
        />
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        {helperText && !error && <p className="text-xs text-slate-400 mt-1">{helperText}</p>}
      </div>
    );
  },
);

Input.displayName = 'Input';
export default Input;
