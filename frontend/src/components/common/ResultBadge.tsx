import React from 'react';
import type { GameResult } from '../../utils/gameResult';

interface ResultBadgeProps {
  result: GameResult;
  /** MyGames uses 'sm' (17px), TeamDetail uses 'md' (18px) — preserved from
   *  before this was shared rather than picked fresh. */
  size?: 'sm' | 'md';
  /** Accessible label, e.g. "Home team won" or "Crimson Tide lost". */
  label: string;
  className?: string;
}

const RESULT_WORD: Record<GameResult, string> = { W: 'Won', L: 'Lost', T: 'Tied' };

const SIZE: Record<'sm' | 'md', string> = {
  sm: 'w-[17px] h-[17px] leading-[17px] text-[9.5px]',
  md: 'w-[18px] h-[18px] leading-[18px] text-[10px]',
};

/** Shared W/L/T square — previously hand-rolled separately in MyGames and
 *  TeamDetail, which had drifted on size (17px/9.5px vs 18px/10px) and on
 *  accessibility (only MyGames carried role="img"/aria-label). */
const ResultBadge: React.FC<ResultBadgeProps> = ({ result, size = 'md', label, className = '' }) => (
  <span
    role="img"
    aria-label={label || RESULT_WORD[result]}
    className={`inline-block rounded text-center font-extrabold text-white shrink-0 ${SIZE[size]} ${
      result === 'W' ? 'bg-win' : result === 'T' ? 'bg-ink-3' : 'bg-loss'
    } ${className}`}
  >
    {result}
  </span>
);

export default ResultBadge;
