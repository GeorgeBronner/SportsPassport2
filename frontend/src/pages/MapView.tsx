import React, { useEffect, useMemo, useState } from 'react';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import SeasonChart from '../components/find/SeasonChart';
import { attendanceApi } from '../api/attendance';
import type { Attendance, AttendanceStats, AttendanceVenuePoint } from '../types/api';
import { LEAGUE_ORDER, leagueColor } from '../utils/leagues';
import { MAP_H, MAP_W, US_PATH, STATE_BORDERS_PATH, projectPoint } from '../components/map/usOutline';
import { formatDateShort } from '../utils/format';

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

/** Atlas: every attended venue on one map — dot size is games, color is league. */
const MapView: React.FC = () => {
  const [venues, setVenues] = useState<AttendanceVenuePoint[]>([]);
  const [withoutVenue, setWithoutVenue] = useState(0);
  const [stats, setStats] = useState<AttendanceStats | null>(null);
  const [attendances, setAttendances] = useState<Attendance[]>([]);
  const [activeLeagues, setActiveLeagues] = useState<Set<string>>(new Set(LEAGUE_ORDER));
  const [selected, setSelected] = useState<AttendanceVenuePoint | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const [loading, setLoading] = useState(true);

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
      .finally(() => setLoading(false));
  }, []);

  const leaguesPresent = useMemo(
    () => new Set(venues.flatMap((v) => v.leagues)),
    [venues]
  );

  const points = useMemo(() => spreadOverlaps(venues), [venues]);

  const visible = points.filter(
    (v) => v.x !== null && v.leagues.some((code) => activeLeagues.has(code))
  );

  const selectedGames = useMemo(() => {
    if (!selected) return [];
    return attendances
      .filter((a) => a.game.venue?.id === selected.venue_id)
      .sort((a, b) => b.game.start_date.localeCompare(a.game.start_date));
  }, [selected, attendances]);

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
            {withoutVenue} attended game{withoutVenue !== 1 ? 's' : ''} missing venue data — not shown
          </span>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_300px] items-stretch">
        <div className="relative bg-panel-2 border border-line rounded-xl overflow-hidden">
          <svg
            viewBox={`0 0 ${MAP_W} ${MAP_H}`}
            className="block w-full h-auto"
            role="img"
            aria-label="Map of venues where you have attended games"
            onMouseLeave={() => setTip(null)}
          >
            <path
              d={US_PATH}
              fill="var(--panel)"
              stroke="var(--line-strong)"
              strokeWidth={1.4}
              strokeLinejoin="round"
            />
            <path
              d={STATE_BORDERS_PATH}
              fill="none"
              stroke="var(--line)"
              strokeWidth={0.75}
              strokeLinejoin="round"
            />
            {[...visible]
              .sort((a, b) => b.count - a.count)
              .map((v) => (
                <circle
                  key={v.venue_id}
                  cx={v.x!}
                  cy={v.y!}
                  r={dotRadius(v.count)}
                  fill={leagueColor(v.leagues[0] ?? '')}
                  fillOpacity={0.85}
                  stroke="var(--page)"
                  strokeWidth={2}
                  className="cursor-pointer"
                  onClick={() => setSelected(v)}
                  onMouseMove={(e) =>
                    setTip({
                      x: e.clientX,
                      y: e.clientY,
                      text: `${v.name} · ${v.count} game${v.count > 1 ? 's' : ''}`,
                    })
                  }
                  onMouseLeave={() => setTip(null)}
                />
              ))}
          </svg>
          <span className="absolute left-3.5 bottom-2.5 text-[11px] italic text-ink-3 font-serif">
            Dot size = games attended · click a dot
          </span>
          {tip && (
            <div
              className="fixed z-30 pointer-events-none bg-panel border border-line-strong rounded-md px-2.5 py-1.5 text-xs text-ink shadow-elevated"
              style={{ left: tip.x + 14, top: tip.y - 34 }}
            >
              {tip.text}
            </div>
          )}
        </div>

        <aside className="bg-panel border border-line rounded-xl p-4 min-h-64">
          {selected ? (
            <>
              <p className="kicker" style={{ color: leagueColor(selected.leagues[0] ?? '') }}>
                {selected.leagues.join(' · ') || 'Venue'}
              </p>
              <h2 className="text-lg font-bold text-ink mt-0.5">{selected.name}</h2>
              <p className="text-xs text-ink-2 mb-2">
                {[selected.city, selected.state].filter(Boolean).join(', ')}
              </p>
              <div className="text-3xl font-bold font-mono text-ink">
                {selected.count}
                <span className="kicker ml-2">game{selected.count !== 1 ? 's' : ''} attended</span>
              </div>
              <ul className="mt-3 border-t border-line max-h-72 overflow-y-auto">
                {selectedGames.map((a) => (
                  <li key={a.id} className="py-2 border-b border-line">
                    <div className="text-[11px] font-mono text-ink-3">
                      {formatDateShort(a.game.start_date, a.game.has_time)}
                    </div>
                    <div className="text-[13px] text-ink">
                      {a.game.away_team.name}{' '}
                      <span className="font-mono">{a.game.away_score ?? ''}</span>
                      <span className="text-ink-3"> at </span>
                      {a.game.home_team.name}{' '}
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
                venue. Toggle leagues with the chips above.
              </p>
            </>
          )}
        </aside>
      </div>

      <div className="bg-panel border border-line rounded-xl p-4 mt-4">
        <h2 className="kicker mb-2">Games per season, all leagues</h2>
        <SeasonChart data={stats?.games_by_season ?? {}} color="var(--focus)" />
      </div>
    </Layout>
  );
};

export default MapView;
