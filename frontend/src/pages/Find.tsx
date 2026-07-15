import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import Omnibox from '../components/find/Omnibox';
import TeamBadge from '../components/common/TeamBadge';
import { attendanceApi } from '../api/attendance';
import type { Attendance, Team } from '../types/api';

interface TeamTally {
  team: Team;
  leagueCode: string;
  count: number;
}

/** Home: the omnibox front and center, with the user's most-seen teams as shortcuts. */
const Find: React.FC = () => {
  const navigate = useNavigate();
  const [attendances, setAttendances] = useState<Attendance[]>([]);

  useEffect(() => {
    attendanceApi.getAttendedGames().then(setAttendances).catch(() => {});
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
    return [...tally.values()].sort((a, b) => b.count - a.count).slice(0, 8);
  }, [attendances]);

  return (
    <Layout>
      <div className="max-w-3xl mx-auto pt-8 md:pt-16">
        <p className="kicker mb-2">Find games</p>
        <h1 className="text-2xl md:text-3xl font-bold mb-6 text-ink">
          Every game you've seen — and every one you haven't. Yet.
        </h1>

        <Omnibox
          autoFocus
          placeholder='Try "Alabama", "Celtics", "Michigan"…'
          onSelect={(team) => navigate(`/teams/${team.id}`)}
        />

        {yourTeams.length > 0 && (
          <div className="mt-10">
            <p className="kicker mb-3">Your teams</p>
            <div className="flex flex-wrap gap-2.5">
              {yourTeams.map(({ team, leagueCode, count }) => (
                <button
                  key={team.id}
                  type="button"
                  onClick={() => navigate(`/teams/${team.id}`)}
                  className="flex items-center gap-2.5 pl-2 pr-3.5 py-1.5 rounded-full bg-panel border border-line hover:border-line-strong transition-colors"
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
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Find;
