import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

const Card: React.FC<CardProps> = ({ children, className = '' }) => {
  return (
    <div className={`card-elevated border border-gray-100 p-5 ${className}`}>
      {children}
    </div>
  );
};

export default Card;
