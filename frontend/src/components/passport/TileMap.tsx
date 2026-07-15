import React from 'react';

// Square tile-grid US map: geographically-sensible neighbor layout, no geodata.
// [state code, column (1-based), row (1-based)]
const TILES: Array<[string, number, number]> = [
  ['AK', 1, 1], ['ME', 12, 1],
  ['WA', 2, 2], ['MT', 3, 2], ['ND', 4, 2], ['MN', 5, 2], ['WI', 6, 2], ['MI', 7, 2],
  ['NY', 10, 2], ['VT', 11, 2], ['NH', 12, 2],
  ['OR', 2, 3], ['ID', 3, 3], ['SD', 4, 3], ['IA', 5, 3], ['IL', 6, 3], ['IN', 7, 3],
  ['OH', 8, 3], ['PA', 9, 3], ['NJ', 10, 3], ['MA', 11, 3], ['RI', 12, 3],
  ['CA', 2, 4], ['NV', 3, 4], ['WY', 4, 4], ['NE', 5, 4], ['MO', 6, 4], ['KY', 7, 4],
  ['WV', 8, 4], ['VA', 9, 4], ['MD', 10, 4], ['DE', 11, 4], ['CT', 12, 4],
  ['UT', 3, 5], ['CO', 4, 5], ['KS', 5, 5], ['AR', 6, 5], ['TN', 7, 5], ['NC', 8, 5], ['SC', 9, 5],
  ['AZ', 3, 6], ['NM', 4, 6], ['OK', 5, 6], ['LA', 6, 6], ['MS', 7, 6], ['AL', 8, 6], ['GA', 9, 6],
  ['HI', 1, 7], ['TX', 5, 7], ['FL', 10, 7],
];

const NAME_TO_CODE: Record<string, string> = {
  alabama: 'AL', alaska: 'AK', arizona: 'AZ', arkansas: 'AR', california: 'CA',
  colorado: 'CO', connecticut: 'CT', delaware: 'DE', florida: 'FL', georgia: 'GA',
  hawaii: 'HI', idaho: 'ID', illinois: 'IL', indiana: 'IN', iowa: 'IA', kansas: 'KS',
  kentucky: 'KY', louisiana: 'LA', maine: 'ME', maryland: 'MD', massachusetts: 'MA',
  michigan: 'MI', minnesota: 'MN', mississippi: 'MS', missouri: 'MO', montana: 'MT',
  nebraska: 'NE', nevada: 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
  'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND',
  ohio: 'OH', oklahoma: 'OK', oregon: 'OR', pennsylvania: 'PA', 'rhode island': 'RI',
  'south carolina': 'SC', 'south dakota': 'SD', tennessee: 'TN', texas: 'TX', utah: 'UT',
  vermont: 'VT', virginia: 'VA', washington: 'WA', 'west virginia': 'WV',
  wisconsin: 'WI', wyoming: 'WY',
};

const toCode = (state: string): string => {
  const s = state.trim();
  return s.length === 2 ? s.toUpperCase() : (NAME_TO_CODE[s.toLowerCase()] ?? s.toUpperCase());
};

// Ink depth by games attended; color-mix keeps it correct in both themes.
const inkFor = (count: number): { bg: string; strong: boolean } => {
  if (count === 0) return { bg: 'var(--panel-2)', strong: false };
  const pct = count >= 20 ? 95 : count >= 10 ? 75 : count >= 7 ? 55 : count >= 3 ? 38 : 20;
  return { bg: `color-mix(in srgb, var(--focus) ${pct}%, var(--panel-2))`, strong: pct >= 55 };
};

interface TileMapProps {
  gamesByState: Record<string, number>;
}

/** "Where you've been": US states as tiles, ink depth = games attended there. */
const TileMap: React.FC<TileMapProps> = ({ gamesByState }) => {
  const counts: Record<string, number> = {};
  for (const [state, count] of Object.entries(gamesByState)) {
    const code = toCode(state);
    counts[code] = (counts[code] ?? 0) + count;
  }

  return (
    <div className="overflow-x-auto">
      <div
        className="grid gap-1 w-max"
        style={{ gridTemplateColumns: 'repeat(12, 2.5rem)', gridAutoRows: '2.5rem' }}
      >
        {TILES.map(([code, col, row]) => {
          const count = counts[code] ?? 0;
          const { bg, strong } = inkFor(count);
          return (
            <div
              key={code}
              title={count ? `${code}: ${count} game${count > 1 ? 's' : ''}` : code}
              className={`rounded flex flex-col items-center justify-center text-[10px] font-semibold border ${
                count === 0 ? 'border-line text-ink-3' : 'border-transparent'
              } ${strong ? 'text-white' : count > 0 ? 'text-ink' : ''}`}
              style={{ gridColumn: col, gridRow: row, backgroundColor: bg }}
            >
              {code}
              {count > 0 && <span className="text-[9px] font-mono font-bold">{count}</span>}
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-2 mt-3 text-xs text-ink-2 flex-wrap">
        <span>Games:</span>
        {([0, 1, 3, 7, 10, 20] as const).map((n, i) => (
          <span key={n} className="inline-flex items-center gap-1">
            <span
              className="inline-block w-5 h-3 rounded-[2px] border border-line"
              style={{ backgroundColor: inkFor(n).bg }}
            />
            {['0', '1–2', '3–6', '7–9', '10–19', '20+'][i]}
          </span>
        ))}
      </div>
    </div>
  );
};

export default TileMap;
