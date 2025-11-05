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

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="bg-gradient-to-br from-primary-50 to-white border-primary-200 !p-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-primary-600 mb-1">{stats.total_games}</div>
              <div className="text-xs text-gray-700 font-medium">Total Games</div>
            </div>
          </Card>

          <Card className="bg-gradient-to-br from-sage-50 to-white border-sage-200 !p-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-sage-600 mb-1">{stats.unique_stadiums}</div>
              <div className="text-xs text-gray-700 font-medium">Stadiums</div>
            </div>
          </Card>

          <Card className="bg-gradient-to-br from-accent-50 to-white border-accent-200 !p-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-accent-600 mb-1">{stats.unique_states}</div>
              <div className="text-xs text-gray-700 font-medium">States</div>
            </div>
          </Card>

          <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-200 !p-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600 mb-1">
                {Object.keys(stats.games_by_team).length}
              </div>
              <div className="text-xs text-gray-700 font-medium">Teams</div>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="bg-gradient-to-br from-primary-50 to-white border-primary-100 !p-5">
            <h2 className="text-lg font-bold text-primary-700 mb-4">Top Teams</h2>
            {topTeams.length === 0 ? (
              <p className="text-gray-600 text-sm">No games attended yet</p>
            ) : (
              <div className="space-y-2">
                {topTeams.map(([team, count]) => (
                  <div key={team} className="flex justify-between items-center p-2 bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow">
                    <span className="text-gray-800 text-sm font-medium truncate pr-2">{team}</span>
                    <span className="font-bold text-primary-600 text-sm flex-shrink-0">{count}</span>
                  </div>
                ))}
              </div>
            )}
            <Link
              to="/statistics"
              className="text-xs text-primary-600 hover:text-primary-700 mt-4 inline-block font-semibold"
            >
              View all stats →
            </Link>
          </Card>

          <Card className="bg-gradient-to-br from-sage-50 to-white border-sage-100 !p-5">
            <h2 className="text-lg font-bold text-sage-700 mb-4">Recent Seasons</h2>
            {recentSeasons.length === 0 ? (
              <p className="text-gray-600 text-sm">No games attended yet</p>
            ) : (
              <div className="space-y-2">
                {recentSeasons.map(([season, count]) => (
                  <div key={season} className="flex justify-between items-center p-2 bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow">
                    <span className="text-gray-800 text-sm font-medium">{season}</span>
                    <span className="font-bold text-sage-600 text-sm">{count} games</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {stats.total_games === 0 && (
          <Card className="mt-6 bg-gradient-to-br from-accent-50 to-white border-accent-100 !p-6">
            <div className="text-center py-6">
              <h3 className="text-xl font-bold text-gray-900 mb-2">
                Start tracking your games
              </h3>
              <p className="text-gray-700 mb-4 text-sm">
                Browse games and mark the ones you've attended to see your statistics here.
              </p>
              <Link
                to="/games"
                className="inline-block px-6 py-2 bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-all shadow-md hover:shadow-lg font-semibold text-sm"
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
