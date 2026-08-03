import React, { useId } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input: React.FC<InputProps> = ({ label, error, className = '', id, ...props }) => {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;

  return (
    <div className="mb-4">
      {label && (
        <label htmlFor={inputId} className="kicker block mb-1.5">
          {label}
        </label>
      )}
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        // `placeholder:text-ink-3` is the fix for placeholders that were
        // rendering at nearly the same lightness as the field itself.
        className={`w-full px-3.5 py-2.5 rounded-lg bg-panel-2 text-ink border
          placeholder:text-ink-3 focus:outline-2 focus:outline-focus transition-colors
          ${error ? 'border-loss' : 'border-line'} ${className}`}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-1.5 text-sm text-loss font-medium">
          {error}
        </p>
      )}
    </div>
  );
};

export default Input;
