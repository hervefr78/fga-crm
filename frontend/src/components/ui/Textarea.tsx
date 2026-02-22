// =============================================================================
// FGA CRM - Composant Textarea reutilisable
// =============================================================================

import { forwardRef, useId } from 'react';
import clsx from 'clsx';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, className, ...props }, ref) => {
    const generatedId = useId();
    const textareaId = props.id || generatedId;

    return (
      <div>
        {label && (
          <label htmlFor={textareaId} className="block text-sm font-medium text-slate-600 mb-1.5">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          className={clsx(
            'w-full px-3.5 py-2.5 bg-slate-50 border rounded-lg text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:border-transparent transition-colors min-h-[80px] resize-y',
            error
              ? 'border-red-300 focus:ring-red-500'
              : 'border-slate-200 focus:ring-primary-500',
            className,
          )}
          {...props}
        />
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      </div>
    );
  },
);

Textarea.displayName = 'Textarea';
export default Textarea;
