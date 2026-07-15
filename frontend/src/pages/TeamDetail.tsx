import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import TeamBadge from '../components/common/TeamBadge';
import Omnibox from '../components/find/Omnibox';
import SeasonChart from '../components/find/SeasonChart';
import { teamsApi } from '../api/teams';
import { gamesApi } from '../api/games';
import { leaguesApi } from '../api/leagues';
import { attendanceApi } from '../api/attendance';
import type { GameListItem, Team, TeamAttendanceStats } from '../types/api';
import { leagueColor } from '../utils/leagues';
import { formatDateShort, yearUTC } from '../utils/format';

const CURRENT_SEASON = new Date().getFullYear();

/** Team workspace: game log with attendance stamps + your record with this team. */
const TeamDetail: React.FC = () => {
  const { id } = useParams();
  const teamId = Number(id);
  const navigate = useNavigate();

  const [team, setTeam] = useState<Team | null>(null);
  const [leagueCode, setLeagueCode] = useState('');
  const [stats, setStats] = useState<TeamAttendanceStats | null>(null);
  const [games, setGames] = useState<GameListItem[]>([]);
  const [attendanceByGame, setAttendanceByGame] = useState<Map<number, number>>(new Map());
  const [season, setSeason] = useState<number | ''>('');
  const [attendedOnly, setAttendedOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadAttendance = useCallback(async () => {
    const attended = await attendanceApi.getAttendedGames();
    setAttendanceByGame(new Map(attended.map((a) => [a.game_id, a.id])));
  }, []);

  useEffect(() => {
    if (!teamId) {
      // Non-numeric :id — nothing will load, so don't sit on the spinner.
      setTeam(null);
      setLoading(false);
      setError('Team not found');
      return;
    }
    setLoading(true);
    // Fresh team, fresh log view: filters follow the season reset.
    setSeason('');
    setAttendedOnly(false);
    let stale = false;
    Promise.all([
      teamsApi.getTeam(teamId),
      teamsApi.getAttendanceStats(teamId),
      leaguesApi.getLeagues(),
      loadAttendance(),
    ])
      .then(([teamData, statsData, leagues]) => {
        if (stale) return;
        setTeam(teamData);
        setStats(statsData);
        setLeagueCode(leagues.find((l) => l.id === teamData.league_id)?.code ?? '');
        setError('');
      })
      .catch(() => {
        if (!stale) setError('Failed to load team');
      })
      .finally(() => {
        if (!stale) setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [teamId, loadAttendance]);

  useEffect(() => {
    if (!teamId) return;
    let stale = false;
    gamesApi
      .getTeamGames(teamId, season === '' ? undefined : season, attendedOnly)
      .then((data) => {
        if (!stale) setGames(data);
      })
      .catch(() => {
        if (!stale) setError('Failed to load games');
      });
    return () => {
      stale = true;
    };
  }, [teamId, season, attendedOnly]);

  const refreshStats = useCallback(() => {
    teamsApi.getAttendanceStats(teamId).then(setStats).catch(() => {});
  }, [teamId]);

  const attend = async (gameId: number) => {
    try {
      const attendance = await attendanceApi.createAttendance({ game_id: gameId });
      setAttendanceByGame((prev) => new Map(prev).set(gameId, attendance.id));
      refreshStats();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to mark game as attended');
    }
  };

  const unattend = async (gameId: number) => {
    const attendanceId = attendanceByGame.get(gameId);
    if (!attendanceId) return;
    try {
      await attendanceApi.deleteAttendance(attendanceId);
      setAttendanceByGame((prev) => {
        const next = new Map(prev);
        next.delete(gameId);
        return next;
      });
      refreshStats();
    } catch {
      setError('Failed to remove attendance');
    }
  };

  const seasonOptions = useMemo(() => {
    if (!team) return [];
    const first = team.first_season ?? CURRENT_SEASON - 30;
    const last = team.last_season ?? CURRENT_SEASON;
    const years = [];
    for (let y = last; y >= first; y--) years.push(y);
    return years;
  }, [team]);

  const visibleGames = attendedOnly ? games.filter((g) => attendanceByGame.has(g.id)) : games;

  if (loading) return <Loading message="Loading team..." />;
  if (!team) {
    return (
      <Layout>
        <Alert type="error" message={error || 'Team not found'} />
      </Layout>
    );
  }

  const color = leagueColor(leagueCode);
  const winRate =
    stats && stats.wins + stats.losses > 0
      ? Math.round((stats.wins / (stats.wins + stats.losses)) * 100)
      : null;

  return (
    <Layout>
      <div className="max-w-xl mb-6">
        <Omnibox
          onSelect={(t) => navigate(`/teams/${t.id}`)}
          placeholder="Switch team…"
          // With nothing typed the tabs aren't filtering a search, so treat
          // the click as "show me my teams in that league" back on Find.
          onLeagueChange={(code, queryEmpty) => {
            if (queryEmpty) navigate(code ? `/?league=${code}` : '/');
          }}
        />
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="flex items-center gap-4 flex-wrap mb-5">
        <TeamBadge
          name={team.name}
          abbreviation={team.abbreviation}
          logoUrl={team.logo_url}
          leagueCode={leagueCode}
          size="lg"
        />
        <div>
          <h1 className="text-2xl font-bold text-ink flex items-center gap-2.5 flex-wrap">
            {team.name}
            {team.nickname && team.nickname !== team.name && (
              <span className="font-normal text-ink-2">{team.nickname}</span>
            )}
            <span
              className="text-[10px] font-extrabold tracking-[0.14em] uppercase text-white rounded px-1.5 py-0.5"
              style={{ backgroundColor: color }}
            >
              {leagueCode}
            </span>
          </h1>
          <p className="text-sm text-ink-2">
            {[team.conference, team.division].filter(Boolean).join(' · ')}
            {stats && stats.games_attended > 0 && (
              <>
                {' '}
                · your log: {stats.games_attended} game{stats.games_attended !== 1 ? 's' : ''}
                {stats.first_game_date &&
                  ` · ${yearUTC(stats.first_game_date)}–${yearUTC(stats.last_game_date!)}`}
              </>
            )}
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px] items-start">
        {/* Game log */}
        <div className="bg-panel border border-line rounded-xl p-4 md:p-5 overflow-x-auto">
          <div className="flex items-center gap-3 flex-wrap mb-3">
            <h2 className="kicker">Game log</h2>
            <div className="ml-auto flex items-center gap-2.5">
              <label className="flex items-center gap-1.5 text-xs text-ink-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={attendedOnly}
                  onChange={(e) => setAttendedOnly(e.target.checked)}
                  className="accent-[var(--stamp)]"
                />
                Attended only
              </label>
              <select
                value={season}
                onChange={(e) => setSeason(e.target.value ? Number(e.target.value) : '')}
                className="text-xs bg-panel-2 text-ink border border-line rounded-md px-2 py-1.5"
                aria-label="Season"
              >
                <option value="">Recent</option>
                {seasonOptions.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {visibleGames.length === 0 ? (
            <p className="text-sm text-ink-3 py-6 text-center">
              {attendedOnly
                ? 'No attended games in this range.'
                : 'No games found for this selection.'}
            </p>
          ) : (
            <table className="w-full text-sm border-collapse min-w-[560px]">
              <thead>
                <tr className="[&>th]:text-left [&>th]:py-1.5 [&>th]:px-2 [&>th]:text-[10px] [&>th]:uppercase [&>th]:tracking-[0.16em] [&>th]:text-ink-3 [&>th]:font-bold [&>th]:border-b [&>th]:border-line-strong">
                  <th>Date</th>
                  <th>Matchup</th>
                  <th>Result</th>
                  <th>Venue</th>
                  <th>Passport</th>
                </tr>
              </thead>
              <tbody>
                {visibleGames.map((game) => {
                  const isHome = game.home_team.id === teamId;
                  const my = isHome ? game.home_score : game.away_score;
                  const opp = isHome ? game.away_score : game.home_score;
                  const played = my !== null && opp !== null;
                  const won = played && my! > opp!;
                  const tied = played && my === opp;
                  const attended = attendanceByGame.has(game.id);
                  return (
                    <tr
                      key={game.id}
                      className={`border-b border-line hover:bg-panel-2 ${attended ? '' : 'opacity-75'}`}
                    >
                      <td className="py-2 px-2 whitespace-nowrap font-mono text-xs text-ink-2">
                        {formatDateShort(game.start_date)}
                      </td>
                      <td className="py-2 px-2">
                        <span className="inline-flex items-center gap-1.5 text-ink flex-wrap">
                          <TeamBadge
                            name={game.away_team.name}
                            abbreviation={game.away_team.abbreviation}
                            logoUrl={game.away_team.logo_url}
                            leagueCode={leagueCode}
                            size="sm"
                          />
                          {game.away_team.name}
                          <span className="text-ink-3">at</span>
                          <TeamBadge
                            name={game.home_team.name}
                            abbreviation={game.home_team.abbreviation}
                            logoUrl={game.home_team.logo_url}
                            leagueCode={leagueCode}
                            size="sm"
                          />
                          {game.home_team.name}
                        </span>
                      </td>
                      <td className="py-2 px-2 whitespace-nowrap font-mono font-bold">
                        {played ? (
                          <>
                            <span
                              className={`inline-block w-[18px] h-[18px] rounded text-center leading-[18px] text-[10px] font-extrabold text-white mr-1.5 ${
                                won ? 'bg-win' : tied ? 'bg-ink-3' : 'bg-loss'
                              }`}
                            >
                              {won ? 'W' : tied ? 'T' : 'L'}
                            </span>
                            <span className="text-ink">
                              {my}–{opp}
                              {game.overtime_flag ? ` ${game.overtime_flag}` : ''}
                            </span>
                          </>
                        ) : (
                          <span className="text-ink-3 font-normal">—</span>
                        )}
                      </td>
                      <td className="py-2 px-2 text-xs text-ink-2">
                        {game.venue
                          ? `${game.venue.name}${game.venue.city ? ` · ${game.venue.city}` : ''}`
                          : ''}
                      </td>
                      <td className="py-2 px-2 whitespace-nowrap">
                        {attended ? (
                          <button
                            type="button"
                            onClick={() => unattend(game.id)}
                            title="Remove attendance"
                            className="stamp-mark cursor-pointer hover:opacity-60"
                          >
                            Attended
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => attend(game.id)}
                            className="text-xs text-ink-3 border border-line rounded px-2 py-0.5 hover:text-ink hover:border-line-strong"
                          >
                            + I was there
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {!attendedOnly && games.length >= 100 && season === '' && (
            <p className="text-xs text-ink-3 pt-3">
              Showing the 100 most recent games — pick a season for older ones.
            </p>
          )}
        </div>

        {/* Stats rail */}
        <div className="flex flex-col gap-4">
          <div className="bg-panel border border-line rounded-xl p-4">
            <h2 className="kicker mb-3">Your {team.name} record</h2>
            <div className="grid grid-cols-2 gap-2.5">
              <div className="bg-panel-2 rounded-lg p-3">
                <div className="text-2xl font-bold font-mono text-ink">
                  {stats?.games_attended ?? 0}
                </div>
                <div className="kicker mt-0.5">Games attended</div>
              </div>
              <div className="bg-panel-2 rounded-lg p-3">
                <div className="text-2xl font-bold font-mono">
                  <span className="text-win">{stats?.wins ?? 0}</span>
                  <span className="text-ink">–</span>
                  <span className="text-loss">{stats?.losses ?? 0}</span>
                  {stats && stats.ties > 0 && <span className="text-ink-2">–{stats.ties}</span>}
                </div>
                <div className="kicker mt-0.5">Record when there</div>
              </div>
              <div className="bg-panel-2 rounded-lg p-3">
                <div className="text-2xl font-bold font-mono text-ink">
                  {stats?.venues.length ?? 0}
                </div>
                <div className="kicker mt-0.5">Venues</div>
              </div>
              <div className="bg-panel-2 rounded-lg p-3">
                <div className="text-2xl font-bold font-mono text-ink">
                  {winRate !== null ? `${winRate}%` : '—'}
                </div>
                <div className="kicker mt-0.5">Win rate</div>
              </div>
            </div>
          </div>

          <div className="bg-panel border border-line rounded-xl p-4">
            <h2 className="kicker mb-3">Games by season</h2>
            <SeasonChart data={stats?.games_by_season ?? {}} color={color} />
          </div>

          {stats && stats.venues.length > 0 && (
            <div className="bg-panel border border-line rounded-xl p-4">
              <h2 className="kicker mb-3">Most-visited venues</h2>
              <div className="flex flex-col gap-2.5">
                {stats.venues.slice(0, 5).map((venue) => {
                  const max = stats.venues[0].count;
                  return (
                    <div key={`${venue.name}-${venue.city}`}>
                      <div className="text-xs text-ink-2 mb-1">{venue.name}</div>
                      <div className="flex items-center gap-2">
                        <span className="block h-2.5 flex-1 rounded-[3px] bg-panel-2 overflow-hidden">
                          <span
                            className="block h-full rounded-r-[3px]"
                            style={{
                              width: `${Math.max((venue.count / max) * 100, 3)}%`,
                              backgroundColor: color,
                            }}
                          />
                        </span>
                        <span className="text-xs font-mono text-ink-2 w-6 text-right">
                          {venue.count}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default TeamDetail;
