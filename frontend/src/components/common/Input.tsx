import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input: React.FC<InputProps> = ({ label, error, className = '', ...props }) => {
  return (
    <div className="mb-5">
      {label && (
        <label className="block text-sm font-bold text-gray-700 mb-2 uppercase tracking-wide">
          {label}
        </label>
      )}
      <input
        className={`w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all ${
          error ? 'border-accent-500 focus:ring-accent-500' : ''
        } ${className}`}
        {...props}
      />
      {error && <p className="mt-2 text-sm text-accent-600 font-medium">{error}</p>}
    </div>
  );
};

export default Input;
