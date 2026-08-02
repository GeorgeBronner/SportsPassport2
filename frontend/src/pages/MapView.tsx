import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import SeasonChart from '../components/find/SeasonChart';
import Tooltip from '../components/common/Tooltip';
import { useTooltip } from '../hooks/useTooltip';
import { attendanceApi } from '../api/attendance';
import type { Attendance, AttendanceStats, AttendanceVenuePoint } from '../types/api';
import { LEAGUE_ORDER, leagueColor } from '../utils/leagues';
import {
  MAP_H,
  MAP_W,
  US_PATH,
  STATE_BORDERS_PATH,
  STATE_PATHS,
  projectPoint,
} from '../components/map/usOutline';
import { countsByStateCode } from '../utils/states';
import { formatDateShort, yearOf } from '../utils/format';

const dotRadius = (count: number) => 3.5 + Math.sqrt(count) * 2;

/** Venues that geocoded to the same city stack — fan them out a few px apart. */
const spreadOverlaps = (venues: AttendanceVenuePoint[]) => {
  const seen = new Map<string, number>();
  return venues.map((v) => {
    if (v.latitude == null || v.longitude == null) return { ...v, x: null, y: null };
    const projected = projectPoint(v.latitude, v.longitude);
    if (!projected) return { ...v, x: null, y: null }; // outside the US (e.g. an international venue)
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
      x: px + Math.cos(angle) * nudge,
      y: py + Math.sin(angle) * nudge,
    };
  });
};

/** Shading for the choropleth, matching the Stats tile-map scale. Kept
 *  deliberately low-contrast so the league-coloured dots stay the top layer. */
const stateFill = (count: number) => {
  if (!count) return 'var(--panel)';
  const pct = count >= 20 ? 40 : count >= 10 ? 30 : count >= 7 ? 22 : count >= 3 ? 15 : 9;
  return `color-mix(in srgb, var(--focus) ${pct}%, var(--panel))`;
};

/** Atlas: every attended venue on one map — dot size is games, color is league. */
const MapView: React.FC = () => {
  const [venues, setVenues] = useState<AttendanceVenuePoint[]>([]);
  const [withoutVenue, setWithoutVenue] = useState(0);
  const [stats, setStats] = useState<AttendanceStats | null>(null);
  const [attendances, setAttendances] = useState<Attendance[]>([]);
  const [activeLeagues, setActiveLeagues] = useState<Set<string>>(new Set(LEAGUE_ORDER));
  const [selected, setSelected] = useState<AttendanceVenuePoint | null>(null);
  const [loading, setLoading] = useState(true);
  const { tip, bind } = useTooltip();

  useEffect(() => {
    Promise.all([
      attendanceApi.getVenues(),
      attendanceApi.getStats(),
      attendanceApi.getAttendedGames(),
    ])
      .then(([venueData, statsData, attendedData]) => {
        setVenues(venueData.venues);
        setWithoutVenue(venueData.games_without_venue);
        setStats(statsData);
        setAttendances(attendedData);
      })
      .catch((err) => console.error('Failed to load map data', err))
      .finally(() => setLoading(false));
  }, []);

  const leaguesPresent = useMemo(() => new Set(venues.flatMap((v) => v.leagues)), [venues]);
  const points = useMemo(() => spreadOverlaps(venues), [venues]);
  const stateCounts = useMemo(
    () => countsByStateCode(stats?.games_by_state ?? {}),
    [stats]
  );

  const visible = points.filter(
    (v) => v.x !== null && v.leagues.some((code) => activeLeagues.has(code))
  );

  const selectedGames = useMemo(() => {
    if (!selected) return [];
    return attendances
      .filter((a) => a.game.venue?.id === selected.venue_id)
      .sort((a, b) => b.game.start_date.localeCompare(a.game.start_date));
  }, [selected, attendances]);

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
    const dates = selectedGames.map((a) => a.game.start_date);
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

  if (loading) return <Loading message="Loading map..." />;

  return (
    <Layout>
      <div className="flex items-baseline gap-4 flex-wrap mb-4">
        <div>
          <p className="kicker">The atlas</p>
          <h1 className="text-2xl font-bold text-ink">Every seat you've ever sat in</h1>
        </div>
        <p className="text-sm text-ink-2 ml-auto">
          <b className="text-ink font-mono">{stats?.total_games ?? 0}</b> games ·{' '}
          <b className="text-ink font-mono">{venues.length}</b> venues ·{' '}
          <b className="text-ink font-mono">{stats?.unique_states ?? 0}</b> states
        </p>
      </div>

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
        {withoutVenue > 0 && (
          <span className="text-xs text-ink-3 self-center ml-2">
            {withoutVenue} attended game{withoutVenue !== 1 ? 's' : ''} missing venue data — not
            shown
          </span>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px] items-stretch">
        <div className="relative bg-panel-2 border border-line rounded-xl overflow-hidden">
          <svg
            viewBox={`0 0 ${MAP_W} ${MAP_H}`}
            className="block w-full h-auto"
            role="img"
            aria-label="Map of venues where you have attended games"
          >
            <path d={US_PATH} fill="var(--panel)" stroke="var(--line-strong)" strokeWidth={1.4} strokeLinejoin="round" />
            {/* Choropleth: the state boundaries were already drawn but carried
                no information. Same scale as the Stats page tile map. */}
            {Object.entries(STATE_PATHS).map(([code, d]) => {
              const count = stateCounts[code] ?? 0;
              if (!count) return null;
              return (
                <path
                  key={code}
                  d={d}
                  fill={stateFill(count)}
                  stroke="none"
                  {...bind({
                    title: code,
                    lines: [`${count} game${count === 1 ? '' : 's'} attended in this state`],
                  })}
                />
              );
            })}
            <path d={STATE_BORDERS_PATH} fill="none" stroke="var(--line)" strokeWidth={0.75} strokeLinejoin="round" />
            {[...visible]
              .sort((a, b) => b.count - a.count)
              .map((v) => {
                const isSelected = selected?.venue_id === v.venue_id;
                return (
                  <circle
                    key={v.venue_id}
                    cx={v.x!}
                    cy={v.y!}
                    r={dotRadius(v.count)}
                    fill={leagueColor(v.leagues[0] ?? '')}
                    // Non-selected dots dim once something is picked, so the
                    // selection is findable on a map with 63 dots.
                    fillOpacity={selected && !isSelected ? 0.4 : 0.85}
                    stroke={isSelected ? 'var(--ink)' : 'var(--page)'}
                    strokeWidth={isSelected ? 2.5 : 2}
                    className="cursor-pointer"
                    onClick={() => setSelected(v)}
                    {...bind({
                      title: v.name,
                      lines: [
                        [v.city, v.state].filter(Boolean).join(', '),
                        `${v.count} game${v.count === 1 ? '' : 's'} attended`,
                        v.leagues.join(' · '),
                      ],
                      color: leagueColor(v.leagues[0] ?? ''),
                    })}
                  />
                );
              })}
          </svg>
          <span className="absolute left-3.5 bottom-2.5 text-[11px] italic text-ink-3 font-serif">
            Dot size = games attended · shading = games per state · click a dot
          </span>
        </div>

        {/* min-h-0 + flex lets the game list grow to the panel instead of being
            capped at max-h-72 with its own scrollbar inside empty space. */}
        <aside className="bg-panel border border-line rounded-xl p-4 flex flex-col min-h-64">
          {selected ? (
            <>
              <div className="flex items-start gap-2">
                <div className="min-w-0">
                  <p
                    className="kicker"
                    style={{ color: leagueColor(selected.leagues[0] ?? '') }}
                  >
                    {selected.leagues.join(' · ') || 'Venue'}
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
                <span className="text-3xl font-bold font-mono text-ink">{selected.count}</span>
                <span className="kicker">game{selected.count !== 1 ? 's' : ''}</span>
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
                <p className="text-[11px] text-ink-3 mt-1">
                  {yearOf(selectedSummary.first, false)}–{yearOf(selectedSummary.last, false)} ·{' '}
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
        </aside>
      </div>

      <div className="bg-panel border border-line rounded-xl p-4 mt-4">
        <h2 className="kicker mb-2">Games per season, all leagues</h2>
        <SeasonChart
          data={stats?.games_by_season ?? {}}
          color="var(--focus)"
          tooltipLines={(year) => {
            const season = stats?.season_breakdown[year];
            if (!season) return [];
            return [
              Object.entries(season.leagues)
                .map(([code, n]) => `${code} ${n}`)
                .join(' · '),
              `${season.venues} venue${season.venues === 1 ? '' : 's'}`,
            ];
          }}
        />
      </div>
      <Tooltip tip={tip} />
    </Layout>
  );
};

export default MapView;
