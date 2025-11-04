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
    <header className="bg-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center space-x-8">
            <Link to="/" className="text-xl font-bold text-gray-900">
              CFB Tracker
            </Link>
            <nav className="hidden md:flex space-x-4">
              <Link to="/" className="text-gray-700 hover:text-gray-900">
                Dashboard
              </Link>
              <Link to="/games" className="text-gray-700 hover:text-gray-900">
                Games
              </Link>
              <Link to="/my-games" className="text-gray-700 hover:text-gray-900">
                My Games
              </Link>
              <Link to="/statistics" className="text-gray-700 hover:text-gray-900">
                Statistics
              </Link>
              {user?.is_admin && (
                <Link to="/admin" className="text-gray-700 hover:text-gray-900">
                  Admin
                </Link>
              )}
            </nav>
          </div>

          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600">{user?.full_name}</span>
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
