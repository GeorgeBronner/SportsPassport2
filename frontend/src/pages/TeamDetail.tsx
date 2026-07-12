import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { teamsApi } from '../api/teams';
import { gamesApi } from '../api/games';
import { attendanceApi } from '../api/attendance';
import type { Team, GameListItem } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import GameCard from '../components/games/GameCard';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';

const TeamDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const teamId = Number(id);

  const [team, setTeam] = useState<Team | null>(null);
  const [franchiseHistory, setFranchiseHistory] = useState<Team[]>([]);
  const [games, setGames] = useState<GameListItem[]>([]);
  const [attendedGameIds, setAttendedGameIds] = useState<Set<number>>(new Set());
  const [gameIdToAttendanceId, setGameIdToAttendanceId] = useState<Map<number, number>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadTeam();
  }, [teamId]);

  const loadTeam = async () => {
    setLoading(true);
    try {
      const [teamData, attendedGames] = await Promise.all([
        teamsApi.getTeam(teamId),
        attendanceApi.getAttendedGames(),
      ]);
      setTeam(teamData);

      const idMap = new Map<number, number>();
      attendedGames.forEach((attendance) => idMap.set(attendance.game_id, attendance.id));
      setGameIdToAttendanceId(idMap);
      setAttendedGameIds(new Set(attendedGames.map((a) => a.game_id)));

      const [historyData, gamesData] = await Promise.all([
        teamData.franchise_id !== null
          ? teamsApi.getTeams({ franchise_id: teamData.franchise_id })
          : Promise.resolve([teamData]),
        gamesApi.getTeamGames(teamId),
      ]);
      // Some adapters (e.g. NHL, see SP3_plan.md) don't populate first_season on
      // teams, so this ordering is best-effort — ties break on id for a stable
      // (not necessarily chronological) result rather than a misleading one.
      setFranchiseHistory(
        [...historyData].sort((a, b) => (a.first_season ?? 0) - (b.first_season ?? 0) || a.id - b.id)
      );
      setGames(gamesData);
    } catch (err) {
      setError('Failed to load team');
    } finally {
      setLoading(false);
    }
  };

  const handleAttend = async (gameId: number, notes?: string) => {
    try {
      const attendance = await attendanceApi.createAttendance({ game_id: gameId, notes });
      setAttendedGameIds(new Set([...attendedGameIds, gameId]));
      setGameIdToAttendanceId(new Map(gameIdToAttendanceId.set(gameId, attendance.id)));
      setSuccess('Game marked as attended!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to mark game as attended');
    }
  };

  const handleRemoveAttendance = async (gameId: number) => {
    try {
      const attendanceId = gameIdToAttendanceId.get(gameId);
      if (!attendanceId) return;
      await attendanceApi.deleteAttendance(attendanceId);

      const newAttendedGameIds = new Set(attendedGameIds);
      newAttendedGameIds.delete(gameId);
      setAttendedGameIds(newAttendedGameIds);

      const newIdMap = new Map(gameIdToAttendanceId);
      newIdMap.delete(gameId);
      setGameIdToAttendanceId(newIdMap);

      setSuccess('Attendance removed!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to remove attendance');
    }
  };

  if (loading) {
    return <Loading message="Loading team..." />;
  }

  if (!team) {
    return (
      <Layout>
        <Card>
          <p className="text-gray-600">Team not found.</p>
        </Card>
      </Layout>
    );
  }

  return (
    <Layout>
      <div>
        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <h1 className="text-4xl font-bold text-gray-900 mb-2">{team.name}</h1>
        <p className="text-gray-600 mb-8">
          {[team.conference, team.division, team.city && team.state ? `${team.city}, ${team.state}` : null]
            .filter(Boolean)
            .join(' • ')}
        </p>

        {franchiseHistory.length > 1 && (
          <Card className="mb-8 bg-gradient-to-br from-sage-50 to-white border-sage-100">
            <h2 className="text-lg font-bold text-sage-700 mb-4">Franchise History</h2>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {franchiseHistory.map((era, i) => (
                <React.Fragment key={era.id}>
                  {i > 0 && <span className="text-gray-400">→</span>}
                  <Link
                    to={`/teams/${era.id}`}
                    className={`px-3 py-2 rounded-lg font-medium transition-colors ${
                      era.id === team.id
                        ? 'bg-sage-600 text-white'
                        : 'bg-white text-gray-700 hover:bg-sage-100 shadow-sm'
                    }`}
                  >
                    {era.name}
                    {era.first_season !== null && (
                      <> ({era.first_season}–{era.last_season ?? 'present'})</>
                    )}
                  </Link>
                </React.Fragment>
              ))}
            </div>
          </Card>
        )}

        <h2 className="text-2xl font-bold text-gray-900 mb-4">Games</h2>
        {games.length === 0 ? (
          <Card className="text-center py-12">
            <p className="text-gray-600 text-lg">No games found for this team.</p>
          </Card>
        ) : (
          <div className="space-y-6">
            {games.map((game) => (
              <GameCard
                key={game.id}
                game={game}
                isAttended={attendedGameIds.has(game.id)}
                onAttend={handleAttend}
                onRemoveAttendance={handleRemoveAttendance}
              />
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default TeamDetail;
