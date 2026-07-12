import React, { useState, useEffect } from 'react';
import { gamesApi } from '../api/games';
import { teamsApi } from '../api/teams';
import { leaguesApi } from '../api/leagues';
import { attendanceApi } from '../api/attendance';
import type { GameListItem, Team, SeasonInfo, League } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import GameCard from '../components/games/GameCard';
import GameFilters from '../components/games/GameFilters';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';

const Games: React.FC = () => {
  const [games, setGames] = useState<GameListItem[]>([]);
  const [leagues, setLeagues] = useState<League[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [seasons, setSeasons] = useState<SeasonInfo[]>([]);
  const [attendedGameIds, setAttendedGameIds] = useState<Set<number>>(new Set());
  const [gameIdToAttendanceId, setGameIdToAttendanceId] = useState<Map<number, number>>(new Map());
  const [selectedLeague, setSelectedLeague] = useState('');
  const [selectedTeam, setSelectedTeam] = useState('');
  const [selectedSeason, setSelectedSeason] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadInitialData();
  }, []);

  // Team/season lists are scoped to the selected league (they stop making
  // sense once narrowed to one league), so reload them whenever it changes.
  useEffect(() => {
    loadTeamsAndSeasons();
  }, [selectedLeague]);

  useEffect(() => {
    loadGames();
  }, [selectedLeague, selectedTeam, selectedSeason]);

  const loadInitialData = async () => {
    try {
      const [leaguesData, attendedGames] = await Promise.all([
        leaguesApi.getLeagues(),
        attendanceApi.getAttendedGames(),
      ]);

      setLeagues(leaguesData);
      setAttendedGameIds(new Set(attendedGames.map((a) => a.game_id)));

      // Build map of game ID to attendance ID
      const idMap = new Map<number, number>();
      attendedGames.forEach((attendance) => {
        idMap.set(attendance.game_id, attendance.id);
      });
      setGameIdToAttendanceId(idMap);
    } catch (err) {
      setError('Failed to load data');
    }
  };

  const loadTeamsAndSeasons = async () => {
    try {
      const [teamsData, seasonsData] = await Promise.all([
        teamsApi.getTeams({ league: selectedLeague || undefined }),
        gamesApi.getSeasons(selectedLeague || undefined),
      ]);
      setTeams(teamsData);
      setSeasons(seasonsData.sort((a, b) => b.season - a.season));
    } catch (err) {
      setError('Failed to load teams/seasons');
    }
  };

  const loadGames = async () => {
    setLoading(true);
    try {
      const gamesData = await gamesApi.getGames({
        league: selectedLeague || undefined,
        team: selectedTeam || undefined,
        season: selectedSeason,
        limit: 100,
      });
      setGames(gamesData);
      setError('');
    } catch (err) {
      setError('Failed to load games');
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
      if (!attendanceId) {
        setError('Attendance record not found');
        return;
      }

      await attendanceApi.deleteAttendance(attendanceId);

      // Update state
      const newAttendedGameIds = new Set(attendedGameIds);
      newAttendedGameIds.delete(gameId);
      setAttendedGameIds(newAttendedGameIds);

      const newIdMap = new Map(gameIdToAttendanceId);
      newIdMap.delete(gameId);
      setGameIdToAttendanceId(newIdMap);

      setSuccess('Attendance removed!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove attendance');
    }
  };

  const handleLeagueChange = (league: string) => {
    setSelectedLeague(league);
    setSelectedTeam('');
    setSelectedSeason(undefined);
  };

  const handleReset = () => {
    setSelectedLeague('');
    setSelectedTeam('');
    setSelectedSeason(undefined);
  };

  return (
    <Layout>
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-8">Browse Games</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <GameFilters
          leagues={leagues}
          teams={teams}
          seasons={seasons}
          selectedLeague={selectedLeague}
          selectedTeam={selectedTeam}
          selectedSeason={selectedSeason}
          onLeagueChange={handleLeagueChange}
          onTeamChange={setSelectedTeam}
          onSeasonChange={setSelectedSeason}
          onReset={handleReset}
        />

        {loading ? (
          <Loading message="Loading games..." />
        ) : games.length === 0 ? (
          <Card className="text-center py-12">
            <p className="text-gray-600 text-lg">No games found. Try adjusting your filters.</p>
          </Card>
        ) : (
          <div>
            <p className="text-sm text-gray-700 mb-8 font-semibold uppercase tracking-wide">
              Showing {games.length} game{games.length !== 1 ? 's' : ''}
            </p>
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
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Games;
