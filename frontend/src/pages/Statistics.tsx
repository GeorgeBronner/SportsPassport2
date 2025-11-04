import React, { useEffect, useState } from 'react';
import { attendanceApi } from '../api/attendance';
import type { AttendanceStats } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Loading from '../components/common/Loading';

const Statistics: React.FC = () => {
  const [stats, setStats] = useState<AttendanceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<'name' | 'count'>('count');

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await attendanceApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Loading message="Loading statistics..." />;
  }

  if (!stats) {
    return (
      <Layout>
        <Card>
          <p className="text-gray-600">Failed to load statistics. Please try again later.</p>
        </Card>
      </Layout>
    );
  }

  const sortedTeams = Object.entries(stats.games_by_team).sort((a, b) => {
    if (sortBy === 'count') {
      return b[1] - a[1];
    }
    return a[0].localeCompare(b[0]);
  });

  const sortedSeasons = Object.entries(stats.games_by_season).sort(
    ([a], [b]) => Number(b) - Number(a)
  );

  return (
    <Layout>
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Statistics</h1>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-blue-600">{stats.total_games}</div>
              <div className="text-sm text-gray-600 mt-1">Total Games Attended</div>
            </div>
          </Card>

          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-green-600">{stats.unique_stadiums}</div>
              <div className="text-sm text-gray-600 mt-1">Unique Stadiums</div>
            </div>
          </Card>

          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-purple-600">{stats.unique_states}</div>
              <div className="text-sm text-gray-600 mt-1">States Visited</div>
            </div>
          </Card>

          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-orange-600">
                {Object.keys(stats.games_by_team).length}
              </div>
              <div className="text-sm text-gray-600 mt-1">Different Teams</div>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <Card>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Games by Team</h2>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'name' | 'count')}
                className="text-sm px-2 py-1 border border-gray-300 rounded"
              >
                <option value="count">Sort by Count</option>
                <option value="name">Sort by Name</option>
              </select>
            </div>
            {sortedTeams.length === 0 ? (
              <p className="text-gray-600">No games attended yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-2">
                {sortedTeams.map(([team, count]) => (
                  <div
                    key={team}
                    className="flex justify-between items-center p-2 hover:bg-gray-50 rounded"
                  >
                    <span className="text-gray-700">{team}</span>
                    <span className="font-semibold text-blue-600">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <h2 className="text-xl font-semibold mb-4">Games by Season</h2>
            {sortedSeasons.length === 0 ? (
              <p className="text-gray-600">No games attended yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-2">
                {sortedSeasons.map(([season, count]) => (
                  <div
                    key={season}
                    className="flex justify-between items-center p-2 hover:bg-gray-50 rounded"
                  >
                    <span className="text-gray-700">{season}</span>
                    <span className="font-semibold text-green-600">{count} games</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <h2 className="text-xl font-semibold mb-4">Stadiums Visited</h2>
            {stats.stadiums_visited.length === 0 ? (
              <p className="text-gray-600">No stadiums visited yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto">
                <ul className="space-y-1">
                  {stats.stadiums_visited.sort().map((stadium) => (
                    <li key={stadium} className="text-gray-700 p-2 hover:bg-gray-50 rounded">
                      {stadium}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <Card>
            <h2 className="text-xl font-semibold mb-4">States Visited</h2>
            {stats.states_visited.length === 0 ? (
              <p className="text-gray-600">No states visited yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto">
                <ul className="space-y-1">
                  {stats.states_visited.sort().map((state) => (
                    <li key={state} className="text-gray-700 p-2 hover:bg-gray-50 rounded">
                      {state}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        </div>
      </div>
    </Layout>
  );
};

export default Statistics;
