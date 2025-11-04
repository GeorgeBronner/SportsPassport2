import React, { useEffect, useState } from 'react';
import { attendanceApi } from '../api/attendance';
import type { AttendanceStats } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Loading from '../components/common/Loading';
import { Link } from 'react-router-dom';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<AttendanceStats | null>(null);
  const [loading, setLoading] = useState(true);

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
    return <Loading message="Loading your stats..." />;
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

  const topTeams = Object.entries(stats.games_by_team)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);

  const recentSeasons = Object.entries(stats.games_by_season)
    .sort(([a], [b]) => Number(b) - Number(a))
    .slice(0, 5);

  return (
    <Layout>
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Dashboard</h1>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-blue-600">{stats.total_games}</div>
              <div className="text-sm text-gray-600 mt-1">Total Games</div>
            </div>
          </Card>

          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-green-600">{stats.unique_stadiums}</div>
              <div className="text-sm text-gray-600 mt-1">Stadiums</div>
            </div>
          </Card>

          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-purple-600">{stats.unique_states}</div>
              <div className="text-sm text-gray-600 mt-1">States</div>
            </div>
          </Card>

          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-orange-600">
                {Object.keys(stats.games_by_team).length}
              </div>
              <div className="text-sm text-gray-600 mt-1">Teams</div>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <h2 className="text-xl font-semibold mb-4">Top Teams</h2>
            {topTeams.length === 0 ? (
              <p className="text-gray-600">No games attended yet</p>
            ) : (
              <div className="space-y-2">
                {topTeams.map(([team, count]) => (
                  <div key={team} className="flex justify-between items-center">
                    <span className="text-gray-700">{team}</span>
                    <span className="font-semibold text-blue-600">{count}</span>
                  </div>
                ))}
              </div>
            )}
            <Link
              to="/statistics"
              className="text-sm text-blue-600 hover:text-blue-700 mt-4 inline-block"
            >
              View all stats →
            </Link>
          </Card>

          <Card>
            <h2 className="text-xl font-semibold mb-4">Recent Seasons</h2>
            {recentSeasons.length === 0 ? (
              <p className="text-gray-600">No games attended yet</p>
            ) : (
              <div className="space-y-2">
                {recentSeasons.map(([season, count]) => (
                  <div key={season} className="flex justify-between items-center">
                    <span className="text-gray-700">{season}</span>
                    <span className="font-semibold text-green-600">{count} games</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {stats.total_games === 0 && (
          <Card className="mt-6">
            <div className="text-center py-8">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Start tracking your games
              </h3>
              <p className="text-gray-600 mb-4">
                Browse games and mark the ones you've attended to see your statistics here.
              </p>
              <Link
                to="/games"
                className="inline-block px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Browse Games
              </Link>
            </div>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
