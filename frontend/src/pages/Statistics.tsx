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
        <h1 className="text-4xl font-bold text-gray-900 mb-8">Statistics</h1>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-10">
          <Card className="bg-gradient-to-br from-primary-50 to-white border-primary-200">
            <div className="text-center">
              <div className="text-5xl font-bold text-primary-600 mb-2">{stats.total_games}</div>
              <div className="text-sm text-gray-700 font-medium uppercase tracking-wide">Total Games Attended</div>
            </div>
          </Card>

          <Card className="bg-gradient-to-br from-sage-50 to-white border-sage-200">
            <div className="text-center">
              <div className="text-5xl font-bold text-sage-600 mb-2">{stats.unique_stadiums}</div>
              <div className="text-sm text-gray-700 font-medium uppercase tracking-wide">Unique Stadiums</div>
            </div>
          </Card>

          <Card className="bg-gradient-to-br from-accent-50 to-white border-accent-200">
            <div className="text-center">
              <div className="text-5xl font-bold text-accent-600 mb-2">{stats.unique_states}</div>
              <div className="text-sm text-gray-700 font-medium uppercase tracking-wide">States Visited</div>
            </div>
          </Card>

          <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-200">
            <div className="text-center">
              <div className="text-5xl font-bold text-blue-600 mb-2">
                {Object.keys(stats.games_by_team).length}
              </div>
              <div className="text-sm text-gray-700 font-medium uppercase tracking-wide">Different Teams</div>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
          <Card className="bg-gradient-to-br from-primary-50 to-white border-primary-100">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-primary-700">Games by Team</h2>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'name' | 'count')}
                className="text-sm px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 font-medium"
              >
                <option value="count">Sort by Count</option>
                <option value="name">Sort by Name</option>
              </select>
            </div>
            {sortedTeams.length === 0 ? (
              <p className="text-gray-600">No games attended yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-3">
                {sortedTeams.map(([team, count]) => (
                  <div
                    key={team}
                    className="flex justify-between items-center p-3 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow"
                  >
                    <span className="text-gray-800 font-medium">{team}</span>
                    <span className="font-bold text-primary-600 text-lg">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="bg-gradient-to-br from-sage-50 to-white border-sage-100">
            <h2 className="text-2xl font-bold text-sage-700 mb-6">Games by Season</h2>
            {sortedSeasons.length === 0 ? (
              <p className="text-gray-600">No games attended yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-3">
                {sortedSeasons.map(([season, count]) => (
                  <div
                    key={season}
                    className="flex justify-between items-center p-3 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow"
                  >
                    <span className="text-gray-800 font-medium">{season}</span>
                    <span className="font-bold text-sage-600 text-lg">{count} games</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <Card className="bg-gradient-to-br from-accent-50 to-white border-accent-100">
            <h2 className="text-2xl font-bold text-accent-700 mb-6">Stadiums Visited</h2>
            {stats.stadiums_visited.length === 0 ? (
              <p className="text-gray-600">No stadiums visited yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto">
                <ul className="space-y-2">
                  {stats.stadiums_visited.sort().map((stadium) => (
                    <li key={stadium} className="text-gray-800 p-3 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow font-medium">
                      {stadium}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-100">
            <h2 className="text-2xl font-bold text-blue-700 mb-6">States Visited</h2>
            {stats.states_visited.length === 0 ? (
              <p className="text-gray-600">No states visited yet</p>
            ) : (
              <div className="max-h-96 overflow-y-auto">
                <ul className="space-y-2">
                  {stats.states_visited.sort().map((state) => (
                    <li key={state} className="text-gray-800 p-3 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow font-medium">
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
