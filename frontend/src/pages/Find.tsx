import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import Omnibox from '../components/find/Omnibox';
import TeamBadge from '../components/common/TeamBadge';
import StampCard from '../components/passport/StampCard';
import { attendanceApi } from '../api/attendance';
import type { Attendance, Team } from '../types/api';
import { leagueColor } from '../utils/leagues';
import { displayTimeZone, formatDateShort, yearOf } from '../utils/format';

interface TeamTally {
  team: Team;
  leagueCode: string;
  count: number;
}

/** Home: the omnibox front and center, with the user's most-seen teams as shortcuts. */
const TOP_TEAMS = 8;
const RECENT_STAMPS = 4;

/** Month/day of a game in the timezone the app displays it in, so an "on this
 *  date" match agrees with the date shown on the row. */
const monthDayOf = (iso: string, hasTime: boolean): string =>
  new Date(iso).toLocaleDateString('en-US', {
    timeZone: displayTimeZone(hasTime),
    month: '2-digit',
    day: '2-digit',
  });

const Find: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const league = searchParams.get('league') ?? '';
  const [attendances, setAttendances] = useState<Attendance[]>([]);
  const [showAllTeams, setShowAllTeams] = useState(false);

  const setLeague = (code: string) => {
    setSearchParams(code ? { league: code } : {}, { replace: true });
    setShowAllTeams(false);
  };

  useEffect(() => {
    attendanceApi
      .getAttendedGames()
      .then(setAttendances)
      // "Your teams" just stays empty on failure — but a silent catch makes
      // that indistinguishable from having logged no games.
      .catch((err) => console.error('Failed to load attended games', err));
  }, []);

  const yourTeams = useMemo<TeamTally[]>(() => {
    const tally = new Map<number, TeamTally>();
    for (const a of attendances) {
      for (const team of [a.game.home_team, a.game.away_team]) {
        const entry = tally.get(team.id) ?? { team, leagueCode: a.game.league.code, count: 0 };
        entry.count += 1;
        tally.set(team.id, entry);
      }
    }
    return [...tally.values()].sort(
      (a, b) => b.count - a.count || a.team.name.localeCompare(b.team.name)
    );
  }, [attendances]);

  const byDate = useMemo(
    () =>
      [...attendances].sort(
        (a, b) => new Date(b.game.start_date).getTime() - new Date(a.game.start_date).getTime()
      ),
    [attendances]
  );

  /** Games played on today's calendar date in any year. */
  const onThisDate = useMemo(() => {
    const today = monthDayOf(new Date().toISOString(), true);
    return byDate.filter((a) => monthDayOf(a.game.start_date, a.game.has_time) === today);
  }, [byDate]);

  const leagueTeams = useMemo(
    () => (league ? yourTeams.filter((t) => t.leagueCode === league) : yourTeams),
    [yourTeams, league]
  );
  const visibleTeams = showAllTeams ? leagueTeams : leagueTeams.slice(0, TOP_TEAMS);

  const todayLabel = new Date().toLocaleDateString('en-US', { day: 'numeric', month: 'long' });

  return (
    <Layout>
      <div className="max-w-5xl mx-auto pt-6 md:pt-10">
        <p className="kicker mb-2">Find games</p>
        <h1 className="text-2xl md:text-3xl font-bold mb-6 text-ink">
          Every game you've seen — and every one you haven't. Yet.
        </h1>

        <div className="max-w-3xl">
          <Omnibox
            autoFocus
            placeholder='Try "Alabama", "Celtics", "Michigan"…'
            onSelect={(team) => navigate(`/teams/${team.id}`)}
            league={league}
            onLeagueChange={setLeague}
          />
        </div>

        {byDate.length > 0 && (
          // items-start so the two panels size to their own content — stretched,
          // the shorter one grew a large empty tail.
          <div className="grid gap-4 lg:grid-cols-2 mt-10 items-start [&>*]:min-w-0">
            <div className="bg-panel border border-line rounded-xl p-4">
              <h2 className="kicker mb-3">On this date · {todayLabel}</h2>
              {onThisDate.length === 0 ? (
                <p className="text-sm text-ink-3 italic font-serif">
                  Nothing in your passport on {todayLabel} — yet. Across {byDate.length} games
                  there's a lot of calendar left.
                </p>
              ) : (
                <div className="flex flex-col gap-2">
                  {onThisDate.map(({ id, game }) => (
                    <div key={id} className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono text-xs text-ink-3 w-9 shrink-0">
                        {yearOf(game.start_date, game.has_time)}
                      </span>
                      <span
                        className="text-[9px] font-extrabold tracking-[0.12em] uppercase text-white rounded px-1.5 py-0.5 shrink-0"
                        style={{ backgroundColor: leagueColor(game.league.code) }}
                      >
                        {game.league.code}
                      </span>
                      <span className="text-sm text-ink">
                        {game.away_team.name} {game.away_score ?? ''}
                        <span className="text-ink-3"> at </span>
                        {game.home_team.name} {game.home_score ?? ''}
                      </span>
                    </div>
                  ))}
                  <p className="text-xs text-ink-3 italic mt-1">
                    {onThisDate.length} game{onThisDate.length === 1 ? '' : 's'} on this date
                    across your log
                  </p>
                </div>
              )}
            </div>

            <div className="bg-panel border border-line rounded-xl p-4">
              <div className="flex items-baseline gap-3 mb-3">
                <h2 className="kicker">Latest stamps</h2>
                <Link to="/my-games" className="ml-auto text-xs text-ink-3 hover:text-ink">
                  Full log →
                </Link>
              </div>
              {/* overflow-y-hidden is explicit: `overflow-x: auto` alone forces
                  the other axis to `auto` too, which gave the rotated stamps a
                  stray vertical scrollbar and clipped their corners. The py
                  clears the rotation's bounding box. */}
              <div className="flex gap-6 items-center overflow-x-auto overflow-y-hidden py-3">
                {byDate.slice(0, RECENT_STAMPS).map((attendance, i) => (
                  <StampCard key={attendance.id} attendance={attendance} index={i} />
                ))}
              </div>
              <p className="text-xs text-ink-3 mt-2">
                Most recent: {formatDateShort(byDate[0].game.start_date, byDate[0].game.has_time)}
              </p>
            </div>
          </div>
        )}

        {yourTeams.length > 0 && (
          <div className="mt-6 bg-panel border border-line rounded-xl p-4">
            <p className="kicker mb-3">Your teams{league ? ` · ${league}` : ''}</p>
            {leagueTeams.length === 0 && (
              <p className="text-sm text-ink-3">No {league} teams in your log yet.</p>
            )}
            <div className="flex flex-wrap gap-2.5">
              {visibleTeams.map(({ team, leagueCode, count }) => (
                <button
                  key={team.id}
                  type="button"
                  onClick={() => navigate(`/teams/${team.id}`)}
                  className="flex items-center gap-2.5 pl-2 pr-3.5 py-1.5 rounded-full bg-panel-2 border border-line hover:border-line-strong transition-colors"
                >
                  <TeamBadge
                    name={team.name}
                    abbreviation={team.abbreviation}
                    logoUrl={team.logo_url}
                    leagueCode={leagueCode}
                    size="sm"
                  />
                  <span className="text-sm text-ink">{team.name}</span>
                  <span className="text-xs text-ink-3 font-mono">{count}</span>
                </button>
              ))}
              {leagueTeams.length > TOP_TEAMS && (
                <button
                  type="button"
                  onClick={() => setShowAllTeams((v) => !v)}
                  className="px-3.5 py-1.5 rounded-full border border-dashed border-line text-sm text-ink-2 hover:text-ink hover:border-line-strong transition-colors"
                >
                  {showAllTeams ? 'Show fewer' : `Show all ${leagueTeams.length} teams`}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Find;
