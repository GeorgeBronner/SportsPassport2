import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Button from '../common/Button';

const Header = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
    setMobileMenuOpen(false);
  };

  const handleNavClick = () => {
    setMobileMenuOpen(false);
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="sticky top-0 z-50 bg-white shadow-md backdrop-blur-sm bg-opacity-95">
      <div className="gradient-primary h-1"></div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-3">
          <div className="flex items-center space-x-6">
            <Link to="/" className="text-xl font-bold text-primary-600 hover:text-primary-700 transition-colors">
              CFB Tracker
            </Link>

            {/* Desktop Navigation */}
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

          {/* Desktop User Info & Logout */}
          <div className="hidden md:flex items-center space-x-3">
            <span className="text-xs text-gray-700 font-medium hidden sm:inline">{user?.full_name}</span>
            <Button variant="secondary" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>

          {/* Mobile Hamburger Button */}
          <button
            className="md:hidden p-2 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
            aria-expanded={mobileMenuOpen}
          >
            <svg
              className="h-6 w-6"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              {mobileMenuOpen ? (
                <path d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu Dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 py-3 space-y-1">
            <div className="px-3 py-2 text-xs text-gray-500 font-medium border-b border-gray-100 mb-2">
              {user?.full_name}
            </div>
            <Link
              to="/"
              className={`block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                isActive('/')
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-primary-600'
              }`}
              onClick={handleNavClick}
            >
              Dashboard
            </Link>
            <Link
              to="/games"
              className={`block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                isActive('/games')
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-primary-600'
              }`}
              onClick={handleNavClick}
            >
              Games
            </Link>
            <Link
              to="/my-games"
              className={`block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                isActive('/my-games')
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-primary-600'
              }`}
              onClick={handleNavClick}
            >
              My Games
            </Link>
            <Link
              to="/statistics"
              className={`block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                isActive('/statistics')
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-primary-600'
              }`}
              onClick={handleNavClick}
            >
              Statistics
            </Link>
            {user?.is_admin && (
              <Link
                to="/admin"
                className={`block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                  isActive('/admin')
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-100 hover:text-primary-600'
                }`}
                onClick={handleNavClick}
              >
                Admin
              </Link>
            )}
            <div className="pt-3 mt-3 border-t border-gray-200">
              <button
                className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-red-600 hover:bg-red-50 transition-colors"
                onClick={handleLogout}
              >
                Logout
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
