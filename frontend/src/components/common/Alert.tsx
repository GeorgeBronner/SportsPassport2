import React from 'react';

interface AlertProps {
  type?: 'info' | 'success' | 'warning' | 'error';
  message: string;
  onClose?: () => void;
}

const Alert: React.FC<AlertProps> = ({ type = 'info', message, onClose }) => {
  const typeClasses = {
    info: 'bg-blue-50 border-blue-400 text-blue-800',
    success: 'bg-sage-50 border-sage-500 text-sage-800',
    warning: 'bg-yellow-50 border-yellow-500 text-yellow-800',
    error: 'bg-accent-50 border-accent-500 text-accent-800',
  };

  return (
    <div className={`border-l-4 p-5 mb-6 rounded-xl shadow-sm ${typeClasses[type]}`}>
      <div className="flex items-center justify-between">
        <p className="font-medium">{message}</p>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-4 text-gray-600 hover:text-gray-800 transition-colors font-bold text-xl"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
};

export default Alert;
