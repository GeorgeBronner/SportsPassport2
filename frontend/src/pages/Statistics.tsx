import React, { useEffect, useState } from 'react';
import { attendanceApi } from '../api/attendance';
import type { AttendanceStats } from '../types/api';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import TileMap from '../components/passport/TileMap';
import SeasonChart from '../components/find/SeasonChart';
import { LEAGUE_ORDER, leagueColor } from '../utils/leagues';
import { yearOf } from '../utils/format';
import { useAuth } from '../hooks/useAuth';

const mrzName = (name: string) =>
  name.toUpperCase().replace(/[^A-Z]+/g, '<');

/** The passport identity page: totals, league stamps, states map, most-seen teams. */
const Statistics: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<AttendanceStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    attendanceApi
      .getStats()
      .then(setStats)
      .catch((err) => {
        console.error('Failed to load statistics', err);
        setStats(null);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading message="Loading statistics..." />;
  if (!stats) {
    return (
      <Layout>
        <p className="text-ink-2">Failed to load statistics. Please try again later.</p>
      </Layout>
    );
  }

  const firstYear = stats.first_game_date ? yearOf(stats.first_game_date, false) : null;
  const lastYear = stats.last_game_date ? yearOf(stats.last_game_date, false) : null;
  const topTeams = Object.entries(stats.games_by_team)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8);
  const maxTeam = topTeams[0]?.[1] ?? 1;

  const leagueSummary = LEAGUE_ORDER
    .filter((code) => stats.games_by_league[code])
    .map((code) => `${code}${stats.games_by_league[code]}`)
    .join('');
  const mrz =
    `P<USASPORTSPASSPORT<<${mrzName(user?.full_name ?? 'BEARER')}` +
    `<<<<${stats.total_games}GM${stats.unique_stadiums}VN${stats.unique_states}ST` +
    `<<${leagueSummary}<<${firstYear ?? ''}${lastYear ? '<' + lastYear : ''}<<`;

  return (
    <Layout>
      <div className="flex items-baseline gap-4 flex-wrap mb-6">
        <div>
          <p className="kicker">Record of travel</p>
          <h1 className="text-2xl font-bold text-ink">Your passport</h1>
        </div>
        {firstYear && (
          <p className="text-sm text-ink-2 ml-auto">
            First entry {firstYear} · latest {lastYear}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[
          [stats.total_games, 'Games attended'],
          [stats.unique_stadiums, 'Venues stamped'],
          [stats.unique_states, 'States entered'],
          [firstYear && lastYear ? `${lastYear - firstYear + 1} yrs` : '—', 'On the road'],
        ].map(([value, label]) => (
          <div key={String(label)} className="bg-panel border border-line rounded-xl p-4">
            <div className="text-3xl font-bold font-mono text-ink">{value}</div>
            <div className="kicker mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="bg-panel border border-line rounded-xl p-4 mb-4">
        <h2 className="kicker mb-3">Games by league</h2>
        <div className="flex flex-wrap gap-2.5">
          {LEAGUE_ORDER.map((code) => {
            const count = stats.games_by_league[code] ?? 0;
            return (
              <div
                key={code}
                className={`flex items-center gap-2 rounded-full border px-3.5 py-2 ${
                  count ? 'border-line-strong' : 'border-line opacity-55'
                }`}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: leagueColor(code) }}
                />
                <span className="text-sm font-semibold text-ink">{code}</span>
                {count ? (
                  <span className="text-sm font-mono font-bold text-ink">{count}</span>
                ) : (
                  <span className="text-[11px] italic text-ink-3">awaiting first stamp</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_340px] items-start mb-4">
        <div className="bg-panel border border-line rounded-xl p-4">
          <h2 className="kicker mb-3">Where you've been</h2>
          <TileMap gamesByState={stats.games_by_state} />
        </div>

        <div className="flex flex-col gap-4">
          <div className="bg-panel border border-line rounded-xl p-4">
            <h2 className="kicker mb-3">Teams seen most</h2>
            {topTeams.length === 0 ? (
              <p className="text-sm text-ink-3">No games attended yet.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {topTeams.map(([team, count]) => (
                  <div key={team} className="flex items-center gap-2">
                    <span className="text-xs text-ink-2 w-32 truncate" title={team}>
                      {team}
                    </span>
                    <span className="block h-2.5 flex-1 rounded-[3px] bg-panel-2 overflow-hidden">
                      <span
                        className="block h-full rounded-r-[3px] bg-focus"
                        style={{ width: `${Math.max((count / maxTeam) * 100, 3)}%` }}
                      />
                    </span>
                    <span className="text-xs font-mono text-ink-2 w-7 text-right">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-panel border border-line rounded-xl p-4">
            <h2 className="kicker mb-3">Games per season</h2>
            <SeasonChart data={stats.games_by_season} color="var(--focus)" />
          </div>
        </div>
      </div>

      <div className="border-y border-line bg-panel-2 rounded-lg px-4 py-3 font-mono text-[13px] tracking-[0.12em] text-ink-2 whitespace-nowrap overflow-x-auto">
        {mrz}
      </div>
    </Layout>
  );
};

export default Statistics;
