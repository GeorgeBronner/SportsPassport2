import React, { useEffect, useRef, useState } from 'react';
import Tooltip from '../common/Tooltip';
import { useTooltip } from '../../hooks/useTooltip';

interface SeasonChartProps {
  data: Record<number, number>;
  color: string;
  /** Drawing height in CSS pixels. Fixed on purpose — see the note below. */
  height?: number;
  /** Extra lines for a bar's hover card, e.g. the league split that season. */
  tooltipLines?: (year: number, count: number) => string[];
}

const PAD_LEFT = 26;
const PAD_RIGHT = 14;
const PAD_TOP = 8;
const PAD_BOTTOM = 20;
const LABEL_PX = 10;

/** Compact games-per-season bar chart.
 *
 * The viewBox tracks the measured container width instead of being fixed at
 * 300, so one SVG unit is always one CSS pixel and **text never scales with
 * the box**. The previous fixed `viewBox="0 0 300 110"` + `w-full` rendered
 * this at 3.9x on the map view — 433px tall with 37px axis numbers — while
 * staying ~1x in the page rails. Height is pinned for the same reason.
 */
const SeasonChart: React.FC<SeasonChartProps> = ({ data, color, height = 132, tooltipLines }) => {
  const hostRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const { tip, bind } = useTooltip();

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(host);
    setWidth(host.clientWidth);
    return () => observer.disconnect();
  }, []);

  const years = Object.keys(data).map(Number);

  // The host div must render even when empty so the observer has something to
  // measure — an early return before it would leave width stuck at 0.
  let body: React.ReactNode = null;

  if (years.length === 0) {
    body = <p className="text-sm text-ink-3">No games attended yet.</p>;
  } else if (width > 0) {
    const y0 = Math.min(...years);
    const y1 = Math.max(...years);
    const span = Math.max(y1 - y0 + 1, 5);
    const plotWidth = Math.max(width - PAD_LEFT - PAD_RIGHT, 10);
    const barWidth = plotWidth / span;
    const max = Math.max(...Object.values(data), 1);
    const gy = (v: number) => height - PAD_BOTTOM - (v / max) * (height - PAD_BOTTOM - PAD_TOP);

    const bars: React.ReactNode[] = [];
    const ticks: React.ReactNode[] = [];
    const tickEvery = span > 20 ? 5 : span > 8 ? 2 : 1;

    for (let y = y0; y <= y1; y++) {
      const value = data[y] || 0;
      const x = PAD_LEFT + (y - y0) * barWidth;
      if (value > 0) {
        const extra = tooltipLines?.(y, value).filter(Boolean) ?? [];
        bars.push(
          // Deliberately not a tab stop. `bind` puts the same text on the bar
          // as an aria-label, so it is in the accessible tree and reachable by
          // element navigation — but making every bar focusable would put 30+
          // tab stops per chart in the way of everything after it.
          <rect
            key={y}
            role="graphics-symbol"
            x={(x + 0.6).toFixed(1)}
            y={gy(value).toFixed(1)}
            width={Math.max(barWidth - 1.6, 1.4).toFixed(1)}
            height={(height - PAD_BOTTOM - gy(value)).toFixed(1)}
            rx={1.5}
            fill={color}
            className="cursor-default hover:opacity-70 transition-opacity"
            {...bind({
              title: `${y} — ${value} game${value === 1 ? '' : 's'}`,
              lines: extra,
              color,
            })}
          />
        );
      }
      if (y % tickEvery === 0) {
        // Centred, the final tick overflowed the right edge and every chart read
        // "'2" instead of "'25". Only the label that would actually overflow is
        // pulled in — anchoring the last one `end` unconditionally shifted it
        // half a label off the gridline the other ticks sit on.
        const centre = x + barWidth / 2;
        const halfLabel = (span > 12 ? 3 : 4) * (LABEL_PX * 0.3);
        const overflows = centre + halfLabel > width - PAD_RIGHT;
        ticks.push(
          <text
            key={`t${y}`}
            x={(overflows ? width - PAD_RIGHT : centre).toFixed(1)}
            y={height - 6}
            textAnchor={overflows ? 'end' : 'middle'}
          >
            {span > 12 ? `'${String(y).slice(2)}` : y}
          </text>
        );
      }
    }

    const gridValues = max >= 4 ? [Math.round(max / 2), max] : [max];

    body = (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        className="block [&_text]:fill-ink-3 [&_text]:font-mono"
        style={{ fontSize: LABEL_PX }}
        role="img"
        aria-label="Attended games per season"
      >
        {gridValues.map((v) => (
          <g key={v}>
            <line
              x1={PAD_LEFT}
              x2={width - PAD_RIGHT}
              y1={gy(v)}
              y2={gy(v)}
              stroke="var(--grid)"
              strokeWidth={1}
            />
            <text x={PAD_LEFT - 5} y={gy(v) + 3.5} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        <line
          x1={PAD_LEFT}
          x2={width - PAD_RIGHT}
          y1={height - PAD_BOTTOM}
          y2={height - PAD_BOTTOM}
          stroke="var(--line-strong)"
          strokeWidth={1}
        />
        {bars}
        {ticks}
      </svg>
    );
  }

  return (
    <div ref={hostRef} style={{ minHeight: years.length ? height : undefined }}>
      {body}
      <Tooltip tip={tip} />
    </div>
  );
};

export default SeasonChart;
