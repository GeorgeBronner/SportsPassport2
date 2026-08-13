import React from 'react';
import { leagueColor } from '../../utils/leagues';

export interface LeagueChipItem {
  /** League code, or '' for a pseudo-entry like "All leagues". */
  code: string;
  /** Defaults to the code itself; used for "All"-style entries. */
  label?: React.ReactNode;
  selected: boolean;
  disabled?: boolean;
  title?: string;
}

interface LeagueChipsProps {
  items: LeagueChipItem[];
  onSelect: (code: string) => void;
  /** Multi-select toggle rows (MapView) dim the dot for a present-but-not-
   *  currently-toggled-on league; single-select filter rows (Omnibox,
   *  MyGames) always show the dot at full strength regardless of selection. */
  dimUnselectedDot?: boolean;
}

/** Shared pill-button row for filtering/toggling by league — single source for
 *  the control that used to be hand-rolled separately in Omnibox, MyGames,
 *  and MapView (and had drifted: different corner radius, different
 *  selected-state background, no aria-pressed anywhere). */
const LeagueChips: React.FC<LeagueChipsProps> = ({ items, onSelect, dimUnselectedDot }) => (
  <div className="flex flex-wrap gap-1.5">
    {items.map((item) => (
      <button
        key={item.code || 'all'}
        type="button"
        disabled={item.disabled}
        title={item.title}
        aria-pressed={item.selected}
        onClick={() => onSelect(item.code)}
        className={`text-[11px] uppercase tracking-[0.12em] px-3 py-1.5 rounded-full border transition-colors ${
          item.disabled
            ? 'border-line text-ink-3 opacity-45 cursor-default'
            : item.selected
              ? 'border-line-strong bg-panel text-ink font-bold'
              : 'border-line text-ink-2 hover:text-ink'
        }`}
      >
        {item.code ? (
          <>
            <span
              className="inline-block w-2 h-2 rounded-full mr-1.5"
              style={{
                backgroundColor: leagueColor(item.code),
                opacity: !dimUnselectedDot || (item.selected && !item.disabled) ? 1 : 0.3,
              }}
            />
            {item.label ?? item.code}
          </>
        ) : (
          item.label
        )}
      </button>
    ))}
  </div>
);

export default LeagueChips;
