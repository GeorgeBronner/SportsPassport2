import React from 'react';
import type { Attendance } from '../../types/api';

const SHAPES = ['rounded-full', 'rounded-[50%/38%]', 'rounded-lg'] as const;
const INKS = ['var(--stamp)', 'var(--lg-cfb)', 'var(--win)'] as const;
const TILTS = [-7, 5, -3, 8, -5, 4] as const;

interface StampCardProps {
  attendance: Attendance;
  index: number;
}

/** Passport entry stamp for one attended game — shape/ink/tilt vary by position. */
const StampCard: React.FC<StampCardProps> = ({ attendance, index }) => {
  const game = attendance.game;
  const shape = SHAPES[index % SHAPES.length];
  const ink = INKS[index % INKS.length];
  const tilt = TILTS[index % TILTS.length];
  const isOval = shape !== 'rounded-lg';

  const date = new Date(game.start_date)
    .toLocaleDateString('en-US', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric' })
    .toUpperCase();

  return (
    <div
      className={`${shape} ${isOval ? 'w-36 h-36' : 'w-40 h-28'} shrink-0 border-[2.5px] flex flex-col items-center justify-center text-center gap-0.5 p-3 font-mono uppercase opacity-90`}
      style={{ borderColor: ink, color: ink, transform: `rotate(${tilt}deg)` }}
    >
      <span className="text-[10px] font-bold tracking-[0.08em] leading-tight">
        {game.venue?.name ?? `${game.away_team.abbreviation ?? game.away_team.name} at ${game.home_team.abbreviation ?? game.home_team.name}`}
      </span>
      {game.venue?.city && (
        <span className="text-[9px] tracking-[0.06em] opacity-80">
          {game.venue.city}{game.venue.state ? ` ${game.venue.state}` : ''}
        </span>
      )}
      <span className="text-[11px] font-bold tracking-[0.06em] mt-0.5">{date}</span>
      <span className="text-[9px] tracking-[0.06em] opacity-80">
        {game.league.code}
        {game.home_score !== null && game.away_score !== null &&
          ` · ${game.away_score}-${game.home_score}`}
      </span>
    </div>
  );
};

export default StampCard;
