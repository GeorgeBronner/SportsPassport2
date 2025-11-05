import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Button from '../common/Button';

const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-50 bg-white shadow-md backdrop-blur-sm bg-opacity-95">
      <div className="gradient-primary h-1"></div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-3">
          <div className="flex items-center space-x-6">
            <Link to="/" className="text-xl font-bold text-primary-600 hover:text-primary-700 transition-colors">
              CFB Tracker
            </Link>
            <nav className="hidden md:flex space-x-4">
              <Link to="/" className="text-sm text-gray-700 hover:text-primary-600 font-medium transition-colors">
                Dashboard
              </Link>
              <Link to="/games" className="text-sm text-gray-700 hover:text-primary-600 font-medium transition-colors">
                Games
              </Link>
              <Link to="/my-games" className="text-sm text-gray-700 hover:text-primary-600 font-medium transition-colors">
                My Games
              </Link>
              <Link to="/statistics" className="text-sm text-gray-700 hover:text-primary-600 font-medium transition-colors">
                Statistics
              </Link>
              {user?.is_admin && (
                <Link to="/admin" className="text-sm text-gray-700 hover:text-primary-600 font-medium transition-colors">
                  Admin
                </Link>
              )}
            </nav>
          </div>

          <div className="flex items-center space-x-3">
            <span className="text-xs text-gray-700 font-medium hidden sm:inline">{user?.full_name}</span>
            <Button variant="secondary" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
