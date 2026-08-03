import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

const Card: React.FC<CardProps> = ({ children, className = '' }) => (
  <div className={`bg-panel border border-line rounded-xl p-5 ${className}`}>{children}</div>
);

export default Card;
