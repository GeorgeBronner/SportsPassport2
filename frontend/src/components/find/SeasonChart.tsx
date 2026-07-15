import React from 'react';

interface SeasonChartProps {
  data: Record<number, number>;
  color: string;
}

/** Compact games-per-season bar chart (SVG). Single series; hairline grid. */
const SeasonChart: React.FC<SeasonChartProps> = ({ data, color }) => {
  const years = Object.keys(data).map(Number);
  if (years.length === 0) {
    return <p className="text-sm text-ink-3">No games attended yet.</p>;
  }

  const y0 = Math.min(...years);
  const y1 = Math.max(...years);
  const span = Math.max(y1 - y0 + 1, 5);
  const W = 300;
  const H = 110;
  const PAD = 18;
  const bw = (W - PAD) / span;
  const max = Math.max(...Object.values(data), 1);
  const gy = (v: number) => H - 18 - (v / max) * (H - 34);

  const bars = [];
  const ticks = [];
  const tickEvery = span > 20 ? 5 : span > 8 ? 2 : 1;
  for (let y = y0; y <= y1; y++) {
    const v = data[y] || 0;
    const x = PAD + (y - y0) * bw;
    if (v > 0) {
      bars.push(
        <rect
          key={y}
          x={(x + 0.5).toFixed(1)}
          y={gy(v).toFixed(1)}
          width={Math.max(bw - 1.6, 1.5).toFixed(1)}
          height={(H - 18 - gy(v)).toFixed(1)}
          rx={1.5}
          fill={color}
        >
          <title>{`${y}: ${v} game${v > 1 ? 's' : ''}`}</title>
        </rect>
      );
    }
    if (y % tickEvery === 0) {
      ticks.push(
        <text key={`t${y}`} x={(x + bw / 2).toFixed(1)} y={H - 5} textAnchor="middle">
          {span > 12 ? `'${String(y).slice(2)}` : y}
        </text>
      );
    }
  }

  const gridVals = max >= 4 ? [Math.round(max / 2), max] : [max];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full [&_text]:fill-ink-3 [&_text]:text-[9.5px] [&_text]:font-mono"
      role="img"
      aria-label="Attended games per season"
    >
      {gridVals.map((v) => (
        <g key={v}>
          <line x1={PAD} x2={W} y1={gy(v)} y2={gy(v)} stroke="var(--grid)" strokeWidth={1} />
          <text x={PAD - 4} y={gy(v) + 3} textAnchor="end">
            {v}
          </text>
        </g>
      ))}
      <line x1={PAD} x2={W} y1={H - 18} y2={H - 18} stroke="var(--line-strong)" strokeWidth={1} />
      {bars}
      {ticks}
    </svg>
  );
};

export default SeasonChart;
