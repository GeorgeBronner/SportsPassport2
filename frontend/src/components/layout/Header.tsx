import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useTheme } from '../../hooks/useTheme';

const NAV = [
  { to: '/', label: 'Find games' },
  { to: '/map', label: 'Map' },
  { to: '/my-games', label: 'My log' },
  { to: '/statistics', label: 'Stats' },
];

const Header = () => {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
    setMobileOpen(false);
  };

  const links = user?.is_admin ? [...NAV, { to: '/admin', label: 'Admin' }] : NAV;

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `text-xs uppercase tracking-[0.12em] pb-1 border-b-2 transition-colors ${
      isActive
        ? 'text-ink border-[var(--focus)]'
        : 'text-ink-2 border-transparent hover:text-ink'
    }`;

  return (
    <header className="sticky top-0 z-40 bg-page/95 backdrop-blur-sm border-b border-line">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center gap-6 py-3">
        <Link to="/" className="leading-tight" onClick={() => setMobileOpen(false)}>
          <span className="block font-extrabold tracking-[0.22em] text-sm text-ink uppercase">
            Sports Passport
          </span>
          <span className="block text-[9px] tracking-[0.14em] text-ink-3 uppercase">
            Games attended · six leagues
          </span>
        </Link>

        <nav className="hidden md:flex items-baseline gap-5 ml-2">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} className={navClass} end={l.to === '/'}>
              {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <button
            type="button"
            onClick={toggle}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            className="p-1.5 rounded-md text-ink-2 hover:text-ink hover:bg-panel-2 transition-colors"
          >
            {theme === 'dark' ? (
              <svg className="w-4.5 h-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </svg>
            ) : (
              <svg className="w-4.5 h-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
              </svg>
            )}
          </button>
          <Link
            to="/profile"
            className="hidden sm:inline text-xs text-ink-2 hover:text-ink transition-colors"
          >
            {user?.full_name}
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="hidden md:inline text-xs uppercase tracking-[0.1em] text-ink-2 hover:text-ink border border-line hover:border-line-strong rounded-md px-3 py-1.5 transition-colors"
          >
            Logout
          </button>

          <button
            type="button"
            className="md:hidden p-2 rounded-md text-ink-2 hover:text-ink"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
            aria-expanded={mobileOpen}
          >
            <svg className="h-5 w-5" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
              {mobileOpen ? <path d="M6 18L18 6M6 6l12 12" /> : <path d="M4 6h16M4 12h16M4 18h16" />}
            </svg>
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t border-line px-4 py-3 space-y-1 bg-page">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-md text-sm ${
                  isActive ? 'bg-panel-2 text-ink font-semibold' : 'text-ink-2 hover:bg-panel-2'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={handleLogout}
            className="block w-full text-left px-3 py-2 rounded-md text-sm text-loss hover:bg-panel-2"
          >
            Logout
          </button>
        </div>
      )}
    </header>
  );
};

export default Header;
