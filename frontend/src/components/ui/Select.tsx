// =============================================================================
// FGA CRM - Composant Select reutilisable
// =============================================================================

import { useId } from 'react';
import clsx from 'clsx';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  label?: string;
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  error?: string;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export default function Select({
  label,
  options,
  value,
  onChange,
  error,
  placeholder,
  className,
  disabled,
}: SelectProps) {
  const generatedId = useId();

  return (
    <div>
      {label && (
        <label htmlFor={generatedId} className="block text-sm font-medium text-slate-600 mb-1.5">
          {label}
        </label>
      )}
      <select
        id={generatedId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={clsx(
          'w-full px-3.5 py-2.5 bg-slate-50 border rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:border-transparent transition-colors',
          error
            ? 'border-red-300 focus:ring-red-500'
            : 'border-slate-200 focus:ring-primary-500',
          disabled && 'opacity-50 cursor-not-allowed',
          className,
        )}
      >
        {placeholder && (
          <option value="">{placeholder}</option>
        )}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
}
