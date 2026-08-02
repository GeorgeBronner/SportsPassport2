import React from 'react';

interface AuthShellProps {
  /** Line under the wordmark — what this particular page is for. */
  tagline: string;
  title: string;
  children: React.ReactNode;
}

/**
 * Signed-out page chrome: wordmark, tagline, and a single panel.
 *
 * Login / Register / ForgotPassword / ResetPassword each carried their own
 * copy of this, on the pre-redesign green-and-white palette, so the signed-out
 * half of the app ignored the theme entirely.
 */
const AuthShell: React.FC<AuthShellProps> = ({ tagline, title, children }) => (
  <div className="min-h-screen bg-page flex items-center justify-center px-4 py-10">
    <div className="max-w-md w-full">
      <div className="text-center mb-8">
        <p className="font-extrabold tracking-[0.22em] text-sm text-ink uppercase">
          Sports Passport
        </p>
        <p className="text-[9px] tracking-[0.14em] text-ink-3 uppercase mt-0.5">
          Games attended · seven leagues
        </p>
        <p className="text-ink-2 mt-4">{tagline}</p>
      </div>

      <div className="bg-panel border border-line rounded-xl p-6 shadow-card">
        <h1 className="text-xl font-bold mb-5 text-ink">{title}</h1>
        {children}
      </div>
    </div>
  </div>
);

export default AuthShell;
