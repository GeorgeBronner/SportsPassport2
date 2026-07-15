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

/** Team logo with a colored-monogram fallback when no logo exists (or fails to load). */
const TeamBadge: React.FC<TeamBadgeProps> = ({ name, abbreviation, logoUrl, leagueCode, size = 'md' }) => {
  const [broken, setBroken] = useState(false);

  if (logoUrl && !broken) {
    return (
      <img
        src={logoUrl}
        alt=""
        aria-hidden="true"
        loading="lazy"
        className={`${SIZES[size]} object-contain shrink-0`}
        onError={() => setBroken(true)}
      />
    );
  }

  const initials = (abbreviation || name.slice(0, 2)).slice(0, 3).toUpperCase();
  return (
    <span
      aria-hidden="true"
      className={`${SIZES[size]} shrink-0 inline-flex items-center justify-center font-extrabold text-white`}
      style={{ backgroundColor: leagueColor(leagueCode) }}
    >
      {initials}
    </span>
  );
};

export default TeamBadge;
