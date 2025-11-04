import React, { useState, useEffect } from 'react';
import { gamesApi } from '../api/games';
import { teamsApi } from '../api/teams';
import { attendanceApi } from '../api/attendance';
import type { GameListItem, Team, SeasonInfo } from '../types/api';
import Layout from '../components/layout/Layout';
import GameCard from '../components/games/GameCard';
import GameFilters from '../components/games/GameFilters';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';

const Games: React.FC = () => {
  const [games, setGames] = useState<GameListItem[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [seasons, setSeasons] = useState<SeasonInfo[]>([]);
  const [attendedGameIds, setAttendedGameIds] = useState<Set<number>>(new Set());
  const [selectedTeam, setSelectedTeam] = useState('');
  const [selectedSeason, setSelectedSeason] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    loadGames();
  }, [selectedTeam, selectedSeason]);

  const loadInitialData = async () => {
    try {
      const [teamsData, seasonsData, attendedGames] = await Promise.all([
        teamsApi.getTeams(),
        gamesApi.getSeasons(),
        attendanceApi.getAttendedGames(),
      ]);

      setTeams(teamsData);
      setSeasons(seasonsData.sort((a, b) => b.season - a.season));
      setAttendedGameIds(new Set(attendedGames.map((a) => a.game_id)));
    } catch (err) {
      setError('Failed to load data');
    }
  };

  const loadGames = async () => {
    setLoading(true);
    try {
      const gamesData = await gamesApi.getGames({
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
      await attendanceApi.createAttendance({ game_id: gameId, notes });
      setAttendedGameIds(new Set([...attendedGameIds, gameId]));
      setSuccess('Game marked as attended!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to mark game as attended');
    }
  };

  const handleReset = () => {
    setSelectedTeam('');
    setSelectedSeason(undefined);
  };

  return (
    <Layout>
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Browse Games</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <GameFilters
          teams={teams}
          seasons={seasons}
          selectedTeam={selectedTeam}
          selectedSeason={selectedSeason}
          onTeamChange={setSelectedTeam}
          onSeasonChange={setSelectedSeason}
          onReset={handleReset}
        />

        {loading ? (
          <Loading message="Loading games..." />
        ) : games.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-600">No games found. Try adjusting your filters.</p>
          </div>
        ) : (
          <div>
            <p className="text-sm text-gray-600 mb-6 font-medium">
              Showing {games.length} game{games.length !== 1 ? 's' : ''}
            </p>
            <div className="space-y-6">
              {games.map((game) => (
                <GameCard
                  key={game.id}
                  game={game}
                  isAttended={attendedGameIds.has(game.id)}
                  onAttend={handleAttend}
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
