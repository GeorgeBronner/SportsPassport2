import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

const BASE =
  'font-semibold rounded-lg transition-colors focus:outline-2 focus:outline-offset-2 focus:outline-focus ' +
  'disabled:opacity-50 disabled:cursor-not-allowed';

const VARIANTS = {
  primary: 'bg-focus text-white hover:opacity-90',
  secondary: 'bg-panel-2 text-ink border border-line hover:border-line-strong',
  danger: 'bg-loss text-white hover:opacity-90',
};

const SIZES = {
  sm: 'px-3.5 py-1.5 text-sm',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-7 py-3 text-base',
};

const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  children,
  className = '',
  ...props
}) => (
  <button className={`${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`} {...props}>
    {children}
  </button>
);

export default Button;
