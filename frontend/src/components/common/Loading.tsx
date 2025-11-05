import React from 'react';

const Loading: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary-200 border-t-primary-600"></div>
      <p className="mt-6 text-gray-700 font-semibold text-lg">{message}</p>
    </div>
  );
};

export default Loading;
