import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { attendanceApi } from '../api/attendance';
import type { AttendanceStats } from '../types/api';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Tooltip from '../components/common/Tooltip';
import { useTooltip } from '../hooks/useTooltip';
import TeamBadge from '../components/common/TeamBadge';
import TileMap from '../components/passport/TileMap';
import SeasonChart from '../components/find/SeasonChart';
import { LEAGUE_ORDER, leagueColor } from '../utils/leagues';
import { formatDateShort, yearOf } from '../utils/format';
import { useAuth } from '../hooks/useAuth';

const mrzName = (name: string) => name.toUpperCase().replace(/[^A-Z]+/g, '<');

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const TOP_TEAM_COUNT = 8;

/** The passport identity page: totals, league stamps, states map, most-seen teams. */
const Statistics: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<AttendanceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const { tip, bind } = useTooltip();

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

  // Every field added in the 2026-08-02 pass is read through `?? {}` / `?? []`.
  // A stale cached bundle against an older API (or the reverse) would otherwise
  // throw here and blank the whole page rather than degrading.
  //
  // Alabama at 149 against a field of 10-29 flattened every other bar into an
  // identical sliver. Scaling to the runner-up keeps the field comparable and
  // marks the leader as off-scale instead of pretending it fits.
  const topTeams = (stats.top_teams ?? []).slice(0, TOP_TEAM_COUNT);
  const runnerUp = topTeams[1]?.count ?? topTeams[0]?.count ?? 1;

  const homeWins = stats.home_wins ?? 0;
  const homeLosses = stats.home_losses ?? 0;
  const homeTies = stats.home_ties ?? 0;
  const played = homeWins + homeLosses + homeTies;
  const homeWinPct = played > 0 ? Math.round((homeWins / played) * 100) : null;

  const busiestWeekday = Object.entries(stats.games_by_weekday ?? {}).sort(
    ([, a], [, b]) => b - a
  )[0];
  const busiestMonth = Object.entries(stats.games_by_month ?? {}).sort(([, a], [, b]) => b - a)[0];

  const leagueSummary = LEAGUE_ORDER.filter((code) => stats.games_by_league[code])
    .map((code) => `${code}${stats.games_by_league[code]}`)
    .join('');
  const mrz =
    `P<USASPORTSPASSPORT<<${mrzName(user?.full_name ?? 'BEARER')}` +
    `<<<<${stats.total_games}GM${stats.unique_stadiums}VN${stats.unique_states}ST` +
    `<<${leagueSummary}<<${firstYear ?? ''}${lastYear ? '<' + lastYear : ''}<<`;

  const heroTiles: Array<{ value: React.ReactNode; label: string; tip: string[] }> = [
    {
      value: stats.total_games,
      label: 'Games attended',
      tip: ['Every game in your log, across all seven leagues.'],
    },
    {
      value: stats.unique_stadiums,
      label: 'Venues stamped',
      tip: ['Distinct venues, counted by id — two venues sharing a name count separately.'],
    },
    {
      value: stats.unique_states,
      label: 'States entered',
      tip: ['States with at least one attended game at a venue we have a location for.'],
    },
    {
      value: firstYear && lastYear ? lastYear - firstYear + 1 : '—',
      label: firstYear && lastYear ? 'Years on the road' : 'On the road',
      tip: firstYear && lastYear ? [`${firstYear} through ${lastYear}, inclusive.`] : [],
    },
  ];

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

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {heroTiles.map((tile) => (
          <div
            key={tile.label}
            className="bg-panel border border-line rounded-xl p-4"
            {...bind({ title: tile.label, lines: tile.tip })}
          >
            <div className="text-3xl font-bold font-mono text-ink">{tile.value}</div>
            <div className="kicker mt-1">{tile.label}</div>
          </div>
        ))}
      </div>

      {/* Second row of totals — all derived from the log, none of it shown before. */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div
          className="bg-panel border border-line rounded-xl p-4"
          {...bind({
            title: 'Home teams when you were there',
            // One string per idea — the card wraps, so pre-split lines just
            // produce ragged half-sentences.
            lines: [
              'There is no "your team" for the log as a whole, so this is the record of the home side in the games you attended.',
              homeWinPct !== null ? `Home sides won ${homeWinPct}% of the time.` : '',
            ],
          })}
        >
          <div className="text-3xl font-bold font-mono">
            <span className="text-win">{homeWins}</span>
            <span className="text-ink">–</span>
            <span className="text-loss">{homeLosses}</span>
            {homeTies > 0 && <span className="text-ink-2">–{homeTies}</span>}
          </div>
          <div className="kicker mt-1">Home teams when there</div>
        </div>

        <div
          className="bg-panel border border-line rounded-xl p-4"
          {...bind({
            title: 'Busiest day of the week',
            lines: busiestWeekday
              ? [`${busiestWeekday[1]} of your ${stats.total_games} games.`]
              : [],
          })}
        >
          <div className="text-3xl font-bold font-mono text-ink">
            {busiestWeekday ? WEEKDAYS[Number(busiestWeekday[0])].slice(0, 3) : '—'}
          </div>
          <div className="kicker mt-1">Busiest day</div>
        </div>

        <div
          className="bg-panel border border-line rounded-xl p-4"
          {...bind({
            title: 'Busiest month',
            lines: busiestMonth
              ? [`${busiestMonth[1]} games in ${MONTHS[Number(busiestMonth[0]) - 1]}.`]
              : [],
          })}
        >
          <div className="text-3xl font-bold font-mono text-ink">
            {busiestMonth ? MONTHS[Number(busiestMonth[0]) - 1].slice(0, 3) : '—'}
          </div>
          <div className="kicker mt-1">Busiest month</div>
        </div>

        <div
          className="bg-panel border border-line rounded-xl p-4"
          {...bind({
            title: 'Longest gap between games',
            lines:
              stats.longest_gap_start && stats.longest_gap_end
                ? [
                    `${formatDateShort(stats.longest_gap_start, false)} → ${formatDateShort(
                      stats.longest_gap_end,
                      false
                    )}`,
                  ]
                : ['Needs at least two attended games.'],
          })}
        >
          <div className="text-3xl font-bold font-mono text-ink">
            {stats.longest_gap_days ?? '—'}
          </div>
          <div className="kicker mt-1">Longest gap (days)</div>
        </div>
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
                {...bind({
                  title: code,
                  lines: count
                    ? [
                        `${count} game${count === 1 ? '' : 's'} — ` +
                          `${Math.round((count / stats.total_games) * 100)}% of your log`,
                      ]
                    : ['No games attended yet.'],
                  color: leagueColor(code),
                })}
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

      <div className="grid gap-4 lg:grid-cols-[1fr_340px] items-start mb-4 [&>*]:min-w-0">
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
              <>
                <div className="flex flex-col gap-2">
                  {topTeams.map((team, i) => {
                    const offScale = i === 0 && team.count > runnerUp;
                    const width = offScale ? 100 : Math.max((team.count / runnerUp) * 100, 3);
                    return (
                      <Link
                        key={team.team_id}
                        to={`/teams/${team.team_id}`}
                        className="flex items-center gap-2 group"
                        {...bind({
                          title: team.name,
                          lines: [
                            `${team.league_code} · ${team.count} game${
                              team.count === 1 ? '' : 's'
                            } — ${Math.round((team.count / stats.total_games) * 100)}% of your log`,
                            offScale ? 'Off-scale: bars are measured against the runner-up.' : '',
                          ],
                          color: leagueColor(team.league_code),
                        })}
                      >
                        <TeamBadge
                          name={team.name}
                          abbreviation={team.abbreviation}
                          logoUrl={team.logo_url}
                          leagueCode={team.league_code}
                          size="sm"
                        />
                        <span className="text-xs text-ink-2 w-24 truncate group-hover:text-ink">
                          {team.name}
                        </span>
                        <span className="block h-2.5 flex-1 rounded-[3px] bg-panel-2 overflow-hidden">
                          <span
                            className="block h-full rounded-r-[3px]"
                            style={{
                              width: `${width}%`,
                              // Hatched fill signals "this bar is clipped", so
                              // the leader can't be misread as merely 100%.
                              background: offScale
                                ? 'repeating-linear-gradient(115deg, var(--focus), var(--focus) 6px,' +
                                  ' color-mix(in srgb, var(--focus) 55%, transparent) 6px,' +
                                  ' color-mix(in srgb, var(--focus) 55%, transparent) 11px)'
                                : 'var(--focus)',
                            }}
                          />
                        </span>
                        <span className="text-xs font-mono text-ink-2 w-7 text-right">
                          {team.count}
                        </span>
                      </Link>
                    );
                  })}
                </div>
                {topTeams[0] && topTeams[0].count > runnerUp && (
                  <p className="text-[11px] text-ink-3 italic mt-2.5">
                    Bars scale to {topTeams[1]?.name}'s {runnerUp}; the leader is hatched to show
                    it runs off the scale.
                  </p>
                )}
              </>
            )}
          </div>

          <div className="bg-panel border border-line rounded-xl p-4">
            <h2 className="kicker mb-3">Games per season</h2>
            <SeasonChart
              data={stats.games_by_season}
              color="var(--focus)"
              tooltipLines={(year) => {
                const season = stats.season_breakdown?.[year];
                if (!season) return [];
                const leagues = Object.entries(season.leagues)
                  .map(([code, n]) => `${code} ${n}`)
                  .join(' · ');
                const newVenues = stats.new_venues_by_season?.[year] ?? 0;
                return [
                  leagues,
                  `${season.venues} venue${season.venues === 1 ? '' : 's'}` +
                    (newVenues ? ` · ${newVenues} new` : ''),
                  `Home teams ${season.home_wins}–${season.home_losses}` +
                    (season.home_ties ? `–${season.home_ties}` : ''),
                ];
              }}
            />
          </div>
        </div>
      </div>

      {stats.venues.length > 0 && (
        <div className="bg-panel border border-line rounded-xl p-4 mb-4">
          <h2 className="kicker mb-3">Most-visited venues</h2>
          <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {stats.venues.slice(0, 8).map((venue) => (
              <div
                key={venue.venue_id}
                    className="flex items-center gap-2"
                {...bind({
                  title: venue.name,
                  lines: [
                    [venue.city, venue.state].filter(Boolean).join(', '),
                    `${venue.count} game${venue.count === 1 ? '' : 's'} attended`,
                  ],
                })}
              >
                <span className="text-xs text-ink-2 w-40 truncate">{venue.name}</span>
                <span className="block h-2.5 flex-1 rounded-[3px] bg-panel-2 overflow-hidden">
                  <span
                    className="block h-full rounded-r-[3px] bg-focus"
                    style={{
                      width: `${Math.max((venue.count / stats.venues[0].count) * 100, 3)}%`,
                    }}
                  />
                </span>
                <span className="text-xs font-mono text-ink-2 w-7 text-right">{venue.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-y border-line bg-panel-2 rounded-lg px-4 py-3 font-mono text-[13px] tracking-[0.12em] text-ink-2 whitespace-nowrap overflow-x-auto">
        {mrz}
      </div>
      <Tooltip tip={tip} />
    </Layout>
  );
};

export default Statistics;
