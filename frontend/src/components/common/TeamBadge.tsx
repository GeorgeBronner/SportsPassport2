import React, { useState } from 'react';
import { leagueColor } from '../../utils/leagues';

interface TeamBadgeProps {
  name: string;
  abbreviation?: string | null;
  logoUrl?: string | null;
  leagueCode: string;
  size?: 'sm' | 'md' | 'lg';
}

const SIZES = {
  sm: 'w-6 h-6 text-[10px] rounded-md',
  md: 'w-8 h-8 text-xs rounded-lg',
  lg: 'w-13 h-13 text-xl rounded-xl',
};

// Corner marker geometry per badge size. It sits on the bottom-right corner and
// overhangs only slightly, so the pair reads as one icon and the layout box is
// unchanged — rows leave as little as 6px between badge and team name.
const MARK_SIZES = {
  sm: 'w-2.5 h-2.5 -right-0.5 -bottom-0.5',
  md: 'w-3 h-3 -right-0.5 -bottom-0.5',
  lg: 'w-4.5 h-4.5 -right-1 -bottom-1',
};

/** Basketball corner marker for college hoops. A school fields both a CFB and a
 *  CBB team under the same name — and often the same logo — so the badge alone
 *  can't tell them apart (see docs/SP3_open_issues.md #2). */
const BasketballMark: React.FC<{ size: keyof typeof MARK_SIZES }> = ({ size }) => (
  <svg
    viewBox="0 0 16 16"
    aria-hidden="true"
    className={`absolute ${MARK_SIZES[size]} rounded-full`}
    // Ring in the surface color so the marker stays legible over a busy logo.
    style={{ boxShadow: '0 0 0 1.5px var(--panel)' }}
  >
    <circle cx="8" cy="8" r="8" fill="var(--lg-cbb)" />
    <g stroke="#fff" strokeWidth="1.3" fill="none">
      <path d="M8 0v16M0 8h16" />
      <path d="M3 1.2C5.6 4.6 5.6 11.4 3 14.8" />
      <path d="M13 1.2C10.4 4.6 10.4 11.4 13 14.8" />
    </g>
  </svg>
);

/** Team logo with a colored-monogram fallback when no logo exists (or fails to load). */
const TeamBadge: React.FC<TeamBadgeProps> = ({ name, abbreviation, logoUrl, leagueCode, size = 'md' }) => {
  // Track which URL failed, not a boolean — the component instance survives
  // client-side navigation between teams, and a new logo deserves a fresh try.
  const [brokenUrl, setBrokenUrl] = useState<string | null>(null);

  const initials = (abbreviation || name.slice(0, 2)).slice(0, 3).toUpperCase();
  const icon =
    logoUrl && brokenUrl !== logoUrl ? (
      <img
        src={logoUrl}
        alt=""
        aria-hidden="true"
        loading="lazy"
        className={`${SIZES[size]} object-contain shrink-0`}
        onError={() => setBrokenUrl(logoUrl)}
      />
    ) : (
      <span
        aria-hidden="true"
        className={`${SIZES[size]} shrink-0 inline-flex items-center justify-center font-extrabold text-white`}
        style={{ backgroundColor: leagueColor(leagueCode) }}
      >
        {initials}
      </span>
    );

  if (leagueCode !== 'CBB') return icon;
  return (
    <span className="relative inline-flex shrink-0">
      {icon}
      <BasketballMark size={size} />
    </span>
  );
};

export default TeamBadge;
