import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import SeasonChart, { type ChartSegment } from '../components/find/SeasonChart';
import Tooltip from '../components/common/Tooltip';
import { useTooltip } from '../hooks/useTooltip';
import { attendanceApi } from '../api/attendance';
import type { Attendance, AttendanceVenuePoint } from '../types/api';
import { LEAGUE_ORDER, leagueColor, sortByLeagueOrder } from '../utils/leagues';
import {
  MAP_H,
  MAP_W,
  US_PATH,
  STATE_BORDERS_PATH,
  STATE_PATHS,
  projectPoint,
} from '../components/map/usOutline';
import { toStateCode } from '../utils/states';
import { formatDateShort, yearOf } from '../utils/format';

const dotRadius = (count: number) => 3.5 + Math.sqrt(count) * 2;

/** Venues that geocoded to the same city stack — fan them out a few px apart.
 *
 * The offset is returned separately from the projected point, in *screen*
 * pixels, because the renderer divides it by the zoom factor. Baked into the
 * coordinate it would scale with the map, and two venues that really share a
 * ground would drift tens of kilometres apart at high zoom — the opposite of
 * what the fan is for. Held constant, it stays the small tie-breaker it is at
 * every level, and genuine geographic separation is what zooming reveals. */
const spreadOverlaps = (venues: AttendanceVenuePoint[]) => {
  const seen = new Map<string, number>();
  return venues.map((v) => {
    const flat = { ...v, x: null, y: null, dx: 0, dy: 0 };
    if (v.latitude == null || v.longitude == null) return flat;
    const projected = projectPoint(v.latitude, v.longitude);
    if (!projected) return flat; // outside the US (e.g. an international venue)
    const key = `${v.latitude.toFixed(3)},${v.longitude.toFixed(3)}`;
    const n = seen.get(key) ?? 0;
    seen.set(key, n + 1);
    // Golden-angle spiral: every duplicate gets a distinct angle and a slowly
    // growing radius, so a 4th+ venue never lands back on an earlier dot.
    const angle = n * 2.39996;
    const nudge = n === 0 ? 0 : 5 + 2 * Math.sqrt(n);
    const [px, py] = projected;
    return {
      ...v,
      x: px,
      y: py,
      dx: Math.cos(angle) * nudge,
      dy: Math.sin(angle) * nudge,
    };
  });
};

/** Shading for the choropleth. Relative to the busiest state *in the current
 *  selection*, not to fixed thresholds — with absolute cutoffs, filtering down
 *  to a league with a handful of games flattened every state to the palest
 *  tint and the layer stopped saying anything. Square-rooted for the same
 *  reason the dots are: one state usually dwarfs the rest.
 *  Kept low-contrast so the league-coloured dots stay the top layer. */
const stateFill = (count: number, max: number) => {
  if (!count) return 'var(--panel)';
  const pct = 9 + 31 * Math.sqrt(count / Math.max(max, 1));
  return `color-mix(in srgb, var(--focus) ${pct.toFixed(1)}%, var(--panel))`;
};

const MIN_ZOOM = 1;
// 40x puts roughly a metro area in the frame. The New York grounds sit 5-20km
// apart, which is about one map unit at continental scale — a lower ceiling
// left them overlapping however far you zoomed, since the dots hold their
// screen size.
const MAX_ZOOM = 40;
const ZOOM_STEP = 1.8;

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

interface Transform {
  k: number;
  x: number;
  y: number;
}

/** Keep the projected map covering the frame: at k=1 the only valid offset is
 *  0, and beyond that you can pan exactly as far as the overhang. */
const clampPan = (t: Transform): Transform => ({
  k: t.k,
  x: clamp(t.x, MAP_W * (1 - t.k), 0),
  y: clamp(t.y, MAP_H * (1 - t.k), 0),
});

/** Client coordinates → untransformed viewBox units. `getScreenCTM` on the
 *  root `<svg>` accounts for the viewBox *and* the letterboxing that
 *  `preserveAspectRatio` adds when the frame is taller than the map, so this
 *  stays correct however the panel is sized. The zoom transform sits on an
 *  inner `<g>`, so what comes back is pre-zoom map space. */
/** League codes seen at a venue, most-attended first. */
const rankLeagues = (leagues: Map<string, number>) =>
  [...leagues.entries()]
    .sort((a, b) => b[1] - a[1] || sortByLeagueOrder(a[0], b[0]))
    .map(([code]) => code);

const toMapPoint = (svg: SVGSVGElement, clientX: number, clientY: number) => {
  const ctm = svg.getScreenCTM();
  if (!ctm) return null;
  const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
  return [p.x, p.y] as const;
};

/** Atlas: every attended venue on one map — dot size is games, color is league. */
const MapView: React.FC = () => {
  const [venues, setVenues] = useState<AttendanceVenuePoint[]>([]);
  const [attendances, setAttendances] = useState<Attendance[]>([]);
  const [activeLeagues, setActiveLeagues] = useState<Set<string>>(new Set(LEAGUE_ORDER));
  const [selected, setSelected] = useState<AttendanceVenuePoint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { tip, bind } = useTooltip();

  useEffect(() => {
    // No /stats call: every number on this page is a *filtered* aggregate, and
    // the endpoint only reports the unfiltered whole. The attended-games list
    // carries league, season and venue on each row, so the page derives its
    // own — one fewer request, and the chips can move everything at once.
    Promise.all([attendanceApi.getVenues(), attendanceApi.getAttendedGames()])
      .then(([venueData, attendedData]) => {
        setVenues(venueData.venues);
        setAttendances(attendedData);
      })
      .catch((err) => {
        console.error('Failed to load map data', err);
        // Without this the page renders "0 games · 0 venues · 0 states" over an
        // empty map, which reads exactly like an empty log.
        setError('Failed to load the map. Please try again later.');
      })
      .finally(() => setLoading(false));
  }, []);

  const leaguesPresent = useMemo(() => new Set(venues.flatMap((v) => v.leagues)), [venues]);
  const points = useMemo(() => spreadOverlaps(venues), [venues]);

  /** Everything the page draws, recomputed from the games whose league is
   *  switched on: dot size and colour, state shading, the season chart and the
   *  venue panel all move together. The /venues payload contributes geometry
   *  and names only — its own counts span every league. */
  const model = useMemo(() => {
    const byVenue = new Map<number, { count: number; leagues: Map<string, number> }>();
    const states: Record<string, number> = {};
    const seasons: Record<number, number> = {};
    const seasonLeagues: Record<number, Record<string, number>> = {};
    const seasonVenues: Record<number, Set<number>> = {};
    let total = 0;
    let withoutVenue = 0;

    for (const a of attendances) {
      const code = a.game.league.code;
      if (!activeLeagues.has(code)) continue;
      total += 1;
      seasons[a.game.season] = (seasons[a.game.season] ?? 0) + 1;
      const split = (seasonLeagues[a.game.season] ??= {});
      split[code] = (split[code] ?? 0) + 1;

      const venue = a.game.venue;
      if (!venue) {
        withoutVenue += 1;
        continue;
      }
      const entry = byVenue.get(venue.id) ?? { count: 0, leagues: new Map() };
      entry.count += 1;
      entry.leagues.set(code, (entry.leagues.get(code) ?? 0) + 1);
      byVenue.set(venue.id, entry);
      (seasonVenues[a.game.season] ??= new Set()).add(venue.id);
      if (venue.state) {
        const sc = toStateCode(venue.state);
        states[sc] = (states[sc] ?? 0) + 1;
      }
    }

    const segments: Record<number, ChartSegment[]> = {};
    for (const [season, split] of Object.entries(seasonLeagues)) {
      // Fixed league order, so a league keeps the same slot in the stack from
      // one bar to the next and the chart reads left-to-right as a trend.
      segments[Number(season)] = Object.keys(split)
        .sort(sortByLeagueOrder)
        .map((code) => ({ key: code, value: split[code], color: leagueColor(code) }));
    }

    return {
      byVenue,
      states,
      seasons,
      seasonVenues,
      segments,
      total,
      withoutVenue,
      maxState: Math.max(0, ...Object.values(states)),
    };
  }, [attendances, activeLeagues]);

  const allLeaguesOn = LEAGUE_ORDER.every((code) => activeLeagues.has(code));

  /** Placed dots, re-counted and re-coloured for the current selection — a
   *  venue you've only seen NHL games at goes NHL-coloured when NBA is off. */
  const visible = useMemo(
    () =>
      points.flatMap((p) => {
        const hit = model.byVenue.get(p.venue_id);
        if (p.x === null || !hit) return [];
        return [{ ...p, count: hit.count, leagues: rankLeagues(hit.leagues) }];
      }),
    [points, model]
  );

  // A venue with nothing left to show can't stay selected, or the panel
  // outlives the dot it belongs to.
  useEffect(() => {
    if (selected && !model.byVenue.has(selected.venue_id)) setSelected(null);
  }, [model, selected]);

  /** Recomputed rather than read off `selected`, whose counts were captured at
   *  click time and would go stale the moment a chip is toggled. */
  const selectedLeagues = useMemo(() => {
    const hit = selected && model.byVenue.get(selected.venue_id);
    return hit ? rankLeagues(hit.leagues) : [];
  }, [selected, model]);

  const selectedGames = useMemo(() => {
    if (!selected) return [];
    return attendances
      .filter(
        (a) =>
          a.game.venue?.id === selected.venue_id && activeLeagues.has(a.game.league.code)
      )
      .sort((a, b) => b.game.start_date.localeCompare(a.game.start_date));
  }, [selected, attendances, activeLeagues]);

  /** Home-team record and the span of visits at the selected venue. */
  const selectedSummary = useMemo(() => {
    if (selectedGames.length === 0) return null;
    let wins = 0;
    let losses = 0;
    let ties = 0;
    const teams = new Map<string, number>();
    for (const { game } of selectedGames) {
      if (game.home_score !== null && game.away_score !== null) {
        if (game.home_score > game.away_score) wins += 1;
        else if (game.home_score < game.away_score) losses += 1;
        else ties += 1;
      }
      for (const team of [game.home_team, game.away_team]) {
        teams.set(team.name, (teams.get(team.name) ?? 0) + 1);
      }
    }
    // Keep has_time alongside the date — yearOf needs it to pick the right
    // timezone, and hard-coding false rolls an evening game back a year on
    // New Year's Eve.
    const dates = selectedGames.map((a) => ({
      date: a.game.start_date,
      hasTime: a.game.has_time,
    }));
    return {
      wins,
      losses,
      ties,
      first: dates[dates.length - 1],
      last: dates[0],
      topTeams: [...teams.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3),
    };
  }, [selectedGames]);

  const toggleLeague = (code: string) => {
    setActiveLeagues((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  // ---- Zoom & pan -------------------------------------------------------
  // The dots around New York overlap into one blob at continental scale, and
  // the golden-angle fan-out only buys a few pixels. Zoom is drawn as a
  // transform on an inner <g> rather than by rewriting the viewBox, so the
  // dots can counter-scale and keep a constant hit target at every level.
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState<Transform>({ k: MIN_ZOOM, x: 0, y: 0 });
  const dragRef = useRef<{ vx: number; vy: number; cx: number; cy: number } | null>(null);
  // Survives past pointerup so the click that follows a drag doesn't also
  // select whatever dot happened to be under the cursor.
  const draggedRef = useRef(false);

  /** Scale about a fixed point in map space, so whatever is under the cursor
   *  stays under the cursor. */
  const zoomAt = useCallback((factor: number, mx: number, my: number) => {
    setZoom((z) => {
      const k = clamp(z.k * factor, MIN_ZOOM, MAX_ZOOM);
      if (k === z.k) return z;
      const ux = (mx - z.x) / z.k;
      const uy = (my - z.y) / z.k;
      return clampPan({ k, x: mx - ux * k, y: my - uy * k });
    });
  }, []);

  /** Zoom by a step about the centre of the frame — what the buttons use.
   *  The anchor is in pre-transform viewBox units, which is exactly the
   *  frame centre whatever the current pan. */
  const zoomStep = (factor: number) => zoomAt(factor, MAP_W / 2, MAP_H / 2);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      // Modifier-gated on purpose: a bare wheel over a map this tall would
      // trap the page scroll, which is the standard complaint about embedded
      // maps. The +/- buttons are the discoverable path.
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const p = toMapPoint(svg, e.clientX, e.clientY);
      if (p) zoomAt(Math.exp(-e.deltaY * 0.002), p[0], p[1]);
    };
    // Non-passive, because React registers its own `onWheel` as passive and
    // preventDefault would be ignored there.
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
    // `loading` is a dependency because the <svg> does not exist on the first
    // commit — without it the listener would never attach.
  }, [zoomAt, loading]);

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    const p = toMapPoint(e.currentTarget, e.clientX, e.clientY);
    if (!p) return;
    dragRef.current = { vx: p[0], vy: p[1], cx: e.clientX, cy: e.clientY };
    draggedRef.current = false;
  };

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const p = toMapPoint(e.currentTarget, e.clientX, e.clientY);
    if (!p) return;
    if (Math.hypot(e.clientX - drag.cx, e.clientY - drag.cy) > 4) draggedRef.current = true;
    const dx = p[0] - drag.vx;
    const dy = p[1] - drag.vy;
    drag.vx = p[0];
    drag.vy = p[1];
    setZoom((z) => clampPan({ ...z, x: z.x + dx, y: z.y + dy }));
  };

  // Pointer capture would retarget the follow-up `click` to the <svg> and
  // break dot selection, so the drag simply ends if the pointer leaves.
  const endDrag = () => {
    dragRef.current = null;
  };

  const zoomed = zoom.k > MIN_ZOOM;

  if (loading) return <Loading message="Loading map..." />;

  return (
    <Layout>
      <div className="flex items-baseline gap-4 flex-wrap mb-4">
        <div>
          <p className="kicker">The atlas</p>
          <h1 className="text-2xl font-bold text-ink">Every seat you've ever sat in</h1>
        </div>
        <p className="text-sm text-ink-2 ml-auto">
          <b className="text-ink font-mono">{model.total}</b> games ·{' '}
          <b className="text-ink font-mono">{model.byVenue.size}</b> venues ·{' '}
          <b className="text-ink font-mono">{Object.keys(model.states).length}</b> states
        </p>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="flex flex-wrap gap-1.5 mb-3">
        {LEAGUE_ORDER.map((code) => {
          const has = leaguesPresent.has(code);
          const on = activeLeagues.has(code);
          return (
            <button
              key={code}
              type="button"
              disabled={!has}
              title={has ? undefined : 'No games attended yet'}
              onClick={() => toggleLeague(code)}
              className={`text-[11px] uppercase tracking-[0.12em] px-3 py-1.5 rounded-full border transition-colors ${
                !has
                  ? 'border-line text-ink-3 opacity-45 cursor-default'
                  : on
                    ? 'border-line-strong bg-panel text-ink font-bold'
                    : 'border-line text-ink-3'
              }`}
            >
              <span
                className="inline-block w-2 h-2 rounded-full mr-1.5"
                style={{ backgroundColor: leagueColor(code), opacity: has && on ? 1 : 0.3 }}
              />
              {code}
            </button>
          );
        })}
        {model.withoutVenue > 0 && (
          <span className="text-xs text-ink-3 self-center ml-2">
            {model.withoutVenue} attended game{model.withoutVenue !== 1 ? 's' : ''} missing venue
            data — not shown
          </span>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px] items-stretch">
        <div className="relative bg-panel-2 border border-line rounded-xl overflow-hidden">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${MAP_W} ${MAP_H}`}
            className={`block w-full h-auto lg:h-full select-none ${
              zoomed ? 'cursor-grab' : ''
            }`}
            // At rest the map has nothing to pan, so a touch gesture belongs to
            // the page; once zoomed the map owns it.
            style={{ touchAction: zoomed ? 'none' : 'pan-y' }}
            role="img"
            aria-label="Map of venues where you have attended games"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerLeave={endDrag}
            onPointerCancel={endDrag}
          >
            {/* Everything geographic lives under one transform. Strokes and dot
                radii divide by k so they stay the same size on screen — the
                point of zooming here is to separate the New York cluster, not
                to inflate it. */}
            <g transform={`translate(${zoom.x} ${zoom.y}) scale(${zoom.k})`}>
              <path
                d={US_PATH}
                fill="var(--panel)"
                stroke="var(--line-strong)"
                strokeWidth={1.4 / zoom.k}
                strokeLinejoin="round"
              />
              {/* Choropleth: the state boundaries were already drawn but carried
                  no information. */}
              {Object.entries(STATE_PATHS).map(([code, d]) => {
                const count = model.states[code] ?? 0;
                if (!count) return null;
                return (
                  <path
                    key={code}
                    role="graphics-symbol"
                    d={d}
                    fill={stateFill(count, model.maxState)}
                    stroke="none"
                    {...bind(
                      {
                        title: code,
                        lines: [`${count} game${count === 1 ? '' : 's'} attended in this state`],
                      },
                      { label: true }
                    )}
                  />
                );
              })}
              <path
                d={STATE_BORDERS_PATH}
                fill="none"
                stroke="var(--line)"
                strokeWidth={0.75 / zoom.k}
                strokeLinejoin="round"
              />
              {[...visible]
                .sort((a, b) => b.count - a.count)
                .map((v) => {
                  const isSelected = selected?.venue_id === v.venue_id;
                  return (
                    <circle
                      key={v.venue_id}
                      // The fan-out offset divides by k so co-located venues
                      // keep a constant screen gap — see spreadOverlaps.
                      cx={v.x! + v.dx / zoom.k}
                      cy={v.y! + v.dy / zoom.k}
                      r={dotRadius(v.count) / zoom.k}
                      fill={leagueColor(v.leagues[0] ?? '')}
                      // Non-selected dots dim once something is picked, so the
                      // selection is findable on a map with 63 dots.
                      fillOpacity={selected && !isSelected ? 0.4 : 0.85}
                      stroke={isSelected ? 'var(--ink)' : 'var(--page)'}
                      strokeWidth={(isSelected ? 2.5 : 2) / zoom.k}
                      className="cursor-pointer focus:outline-2 focus:outline-focus"
                      // Selecting a venue was mouse-only — these are the map's
                      // primary control, so unlike the chart bars they earn a tab
                      // stop. Focus also surfaces the tooltip, which is what makes
                      // the dots usable on touch.
                      role="button"
                      tabIndex={0}
                      aria-pressed={isSelected}
                      // A pan that happens to start on a dot must not also
                      // select it.
                      onClick={() => {
                        if (!draggedRef.current) setSelected(v);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelected(v);
                        }
                      }}
                      {...bind(
                        {
                          title: v.name,
                          lines: [
                            [v.city, v.state].filter(Boolean).join(', '),
                            `${v.count} game${v.count === 1 ? '' : 's'} attended`,
                            v.leagues.join(' · '),
                          ],
                          color: leagueColor(v.leagues[0] ?? ''),
                        },
                        { label: true }
                      )}
                    />
                  );
                })}
            </g>
          </svg>

          <div className="absolute right-2.5 top-2.5 flex flex-col gap-1">
            {[
              {
                label: '+',
                title: 'Zoom in',
                run: () => zoomStep(ZOOM_STEP),
                off: zoom.k >= MAX_ZOOM,
              },
              { label: '−', title: 'Zoom out', run: () => zoomStep(1 / ZOOM_STEP), off: !zoomed },
            ].map((b) => (
              <button
                key={b.label}
                type="button"
                title={b.title}
                aria-label={b.title}
                disabled={b.off}
                onClick={b.run}
                className="w-7 h-7 rounded-md border border-line bg-panel text-ink text-base leading-none
                           hover:bg-panel-2 disabled:opacity-40 disabled:cursor-default"
              >
                {b.label}
              </button>
            ))}
            {zoomed && (
              <button
                type="button"
                title="Reset zoom"
                aria-label="Reset zoom"
                onClick={() => setZoom({ k: MIN_ZOOM, x: 0, y: 0 })}
                className="w-7 h-7 rounded-md border border-line bg-panel text-ink text-[11px] leading-none
                           hover:bg-panel-2"
              >
                ⤢
              </button>
            )}
          </div>

          <span className="absolute left-3.5 bottom-2.5 text-[11px] italic text-ink-3 font-serif">
            Dot size = games attended · shading = games per state · click a dot
            {zoomed ? ' · drag to pan' : ''}
          </span>
        </div>

        {/* The panel is capped at the map's height and the game list scrolls
            inside it. A venue with 76 games would otherwise stretch the grid
            row far past the map and push the season chart off-screen.
            The inner wrapper is absolutely positioned from `lg` up so the
            panel contributes no intrinsic height — the row is then sized by
            the map alone and `items-stretch` gives this column the same
            height back. Below `lg` the columns stack and natural flow is
            what you want, so the wrapper stays static there.

            The `lg` floor is what makes six game rows fit. The map's own
            height left the list 310px — 5.7 rows — so the sixth was always
            clipped just short of readable. 499px = the 158px header block +
            six 54px rows + the panel's bottom padding and border; the map is
            `h-full` and centres inside the slightly taller frame. Fixed
            rather than measured on purpose: a floor that tracked the selected
            venue's header would resize the map under the cursor every time
            you clicked a different dot. */}
        <aside className="relative bg-panel border border-line rounded-xl min-h-64 lg:min-h-[499px]">
          <div className="lg:absolute lg:inset-0 p-4 flex flex-col">
          {selected ? (
            <>
              <div className="flex items-start gap-2">
                <div className="min-w-0">
                  <p
                    className="kicker"
                    style={{ color: leagueColor(selectedLeagues[0] ?? '') }}
                  >
                    {selectedLeagues.join(' · ') || 'Venue'}
                  </p>
                  <h2 className="text-lg font-bold text-ink mt-0.5">{selected.name}</h2>
                  <p className="text-xs text-ink-2">
                    {[selected.city, selected.state].filter(Boolean).join(', ')}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  aria-label="Clear selection"
                  className="ml-auto text-ink-3 hover:text-ink text-lg leading-none shrink-0"
                >
                  ×
                </button>
              </div>

              <div className="flex items-baseline gap-3 flex-wrap mt-2.5">
                <span className="text-3xl font-bold font-mono text-ink">
                  {selectedGames.length}
                </span>
                <span className="kicker">game{selectedGames.length !== 1 ? 's' : ''}</span>
                {selectedSummary && (
                  <span className="ml-auto text-xs font-mono">
                    <span className="text-win">{selectedSummary.wins}</span>
                    <span className="text-ink-2">–</span>
                    <span className="text-loss">{selectedSummary.losses}</span>
                    {selectedSummary.ties > 0 && (
                      <span className="text-ink-2">–{selectedSummary.ties}</span>
                    )}
                    <span className="text-ink-3"> home</span>
                  </span>
                )}
              </div>

              {selectedSummary && (
                // One line, always — the six-row budget above assumes a
                // header of known height, and three long team names would
                // wrap this to two and eat a row.
                <p className="text-[11px] text-ink-3 mt-1 truncate">
                  {yearOf(selectedSummary.first.date, selectedSummary.first.hasTime)}–
                  {yearOf(selectedSummary.last.date, selectedSummary.last.hasTime)} ·{' '}
                  {selectedSummary.topTeams.map(([name, n]) => `${name} ${n}`).join(' · ')}
                </p>
              )}

              <ul className="mt-3 border-t border-line flex-1 overflow-y-auto min-h-0">
                {selectedGames.map((a) => (
                  <li key={a.id} className="py-2 border-b border-line">
                    <div className="text-[11px] font-mono text-ink-3">
                      {formatDateShort(a.game.start_date, a.game.has_time)}
                    </div>
                    <div className="text-[13px] text-ink">
                      <Link to={`/teams/${a.game.away_team.id}`} className="hover:underline">
                        {a.game.away_team.name}
                      </Link>{' '}
                      <span className="font-mono">{a.game.away_score ?? ''}</span>
                      <span className="text-ink-3"> at </span>
                      <Link to={`/teams/${a.game.home_team.id}`} className="hover:underline">
                        {a.game.home_team.name}
                      </Link>{' '}
                      <span className="font-mono">{a.game.home_score ?? ''}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <p className="kicker">Venue</p>
              <h2 className="text-lg font-bold text-ink mt-0.5">Click a dot</h2>
              <p className="text-sm text-ink-3 italic font-serif mt-3">
                Dot size is games attended there; color is the league you've seen most at that
                venue. State shading is games attended in that state. Toggle leagues with the
                chips above.
              </p>
            </>
          )}
          </div>
        </aside>
      </div>

      <div className="bg-panel border border-line rounded-xl p-4 mt-4">
        <h2 className="kicker mb-2">
          Games per season, {allLeaguesOn ? 'all leagues' : 'selected leagues'}
        </h2>
        {/* Each bar is stacked in the league colours of the chips above, so a
            season reads as a mix rather than a single number. The chips are
            the legend — there is no second one. */}
        <SeasonChart
          data={model.seasons}
          color="var(--focus)"
          segments={model.segments}
          tooltipLines={(year) => {
            const split = model.segments[year];
            if (!split) return [];
            const venueCount = model.seasonVenues[year]?.size ?? 0;
            return [
              split.map((s) => `${s.key} ${s.value}`).join(' · '),
              `${venueCount} venue${venueCount === 1 ? '' : 's'}`,
            ];
          }}
        />
      </div>
      <Tooltip tip={tip} />
    </Layout>
  );
};

export default MapView;
