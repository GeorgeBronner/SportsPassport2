import React from 'react';
import Tooltip from '../common/Tooltip';
import { useTooltip } from '../../hooks/useTooltip';
import { countsByStateCode } from '../../utils/states';

// Square tile-grid US map: geographically-sensible neighbor layout, no geodata.
// [state code, column (1-based), row (1-based)]
//
// Continental only, matching the Atlas view — which drops Alaska and Hawaii
// from the projection (see docs/SP3_frontend_redesign.md Phase 4). Keeping
// them here left two marooned tiles and an empty column for a dataset with no
// non-continental games. Column 1 goes with them, so the grid is 11 wide.
const TILES: Array<[string, number, number]> = [
  ['ME', 11, 1],
  ['WA', 1, 2], ['MT', 2, 2], ['ND', 3, 2], ['MN', 4, 2], ['WI', 5, 2], ['MI', 6, 2],
  ['NY', 9, 2], ['VT', 10, 2], ['NH', 11, 2],
  ['OR', 1, 3], ['ID', 2, 3], ['SD', 3, 3], ['IA', 4, 3], ['IL', 5, 3], ['IN', 6, 3],
  ['OH', 7, 3], ['PA', 8, 3], ['NJ', 9, 3], ['MA', 10, 3], ['RI', 11, 3],
  ['CA', 1, 4], ['NV', 2, 4], ['WY', 3, 4], ['NE', 4, 4], ['MO', 5, 4], ['KY', 6, 4],
  ['WV', 7, 4], ['VA', 8, 4], ['MD', 9, 4], ['DE', 10, 4], ['CT', 11, 4],
  ['UT', 2, 5], ['CO', 3, 5], ['KS', 4, 5], ['AR', 5, 5], ['TN', 6, 5], ['NC', 7, 5],
  ['SC', 8, 5],
  ['AZ', 2, 6], ['NM', 3, 6], ['OK', 4, 6], ['LA', 5, 6], ['MS', 6, 6], ['AL', 7, 6],
  ['GA', 8, 6],
  ['TX', 4, 7], ['FL', 9, 7],
];

/** Ink depth by games attended. The unvisited step is a hairline outline rather
 *  than a tint — at 20% focus over panel-2 the "1–2" swatch was almost
 *  indistinguishable from "0" in dark mode. */
const inkFor = (count: number): { bg: string; strong: boolean } => {
  if (count === 0) return { bg: 'transparent', strong: false };
  const pct = count >= 20 ? 95 : count >= 10 ? 75 : count >= 7 ? 55 : count >= 3 ? 38 : 26;
  return { bg: `color-mix(in srgb, var(--focus) ${pct}%, var(--panel-2))`, strong: pct >= 55 };
};

const LEGEND: Array<[number, string]> = [
  [0, '0'],
  [1, '1–2'],
  [3, '3–6'],
  [7, '7–9'],
  [10, '10–19'],
  [20, '20+'],
];

interface TileMapProps {
  gamesByState: Record<string, number>;
}

const TILED = new Set(TILES.map(([code]) => code));

/** "Where you've been": US states as tiles, ink depth = games attended there. */
const TileMap: React.FC<TileMapProps> = ({ gamesByState }) => {
  const counts = countsByStateCode(gamesByState);
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  // Anything the grid has no tile for — AK, HI, DC, or a foreign venue whose
  // state slipped through. Without this they'd vanish silently while still
  // counting toward "states entered" and skewing every tile's percentage.
  const untiled = Object.entries(counts).filter(([code]) => !TILED.has(code));
  const { tip, bind } = useTooltip();

  return (
    <div className="overflow-x-auto">
      <div
        className="grid gap-1 w-max"
        style={{ gridTemplateColumns: 'repeat(11, 2.5rem)', gridAutoRows: '2.5rem' }}
      >
        {TILES.map(([code, col, row]) => {
          const count = counts[code] ?? 0;
          const { bg, strong } = inkFor(count);
          return (
            <div
              key={code}
              role="img"
              className={`rounded flex flex-col items-center justify-center text-[10px] font-semibold border ${
                count === 0 ? 'border-line text-ink-3' : 'border-transparent'
              } ${strong ? 'text-white' : count > 0 ? 'text-ink' : ''}`}
              style={{ gridColumn: col, gridRow: row, backgroundColor: bg }}
              {...bind({
                title: code,
                lines: count
                  ? [
                      `${count} game${count === 1 ? '' : 's'} attended`,
                      total ? `${Math.round((count / total) * 100)}% of your located games` : '',
                    ]
                  : ['No games attended here yet.'],
              })}
            >
              {code}
              {count > 0 && <span className="text-[9px] font-mono font-bold">{count}</span>}
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-2 mt-3 text-xs text-ink-2 flex-wrap">
        <span>Games:</span>
        {LEGEND.map(([n, label]) => (
          <span key={n} className="inline-flex items-center gap-1">
            <span
              className="inline-block w-5 h-3 rounded-[2px] border border-line"
              style={{ backgroundColor: inkFor(n).bg }}
            />
            {label}
          </span>
        ))}
      </div>
      {untiled.length > 0 && (
        <p className="text-[11px] text-ink-3 italic mt-2">
          Off the grid:{' '}
          {untiled
            .sort(([, a], [, b]) => b - a)
            .map(([code, count]) => `${code} ${count}`)
            .join(' · ')}
        </p>
      )}
      <Tooltip tip={tip} />
    </div>
  );
};

export default TileMap;
