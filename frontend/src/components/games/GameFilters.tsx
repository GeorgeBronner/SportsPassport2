import React, { useEffect, useState } from 'react';
import type { Team, SeasonInfo } from '../../types/api';

interface GameFiltersProps {
  teams: Team[];
  seasons: SeasonInfo[];
  selectedTeam: string;
  selectedSeason: number | undefined;
  onTeamChange: (team: string) => void;
  onSeasonChange: (season: number | undefined) => void;
  onReset: () => void;
}

const GameFilters: React.FC<GameFiltersProps> = ({
  teams,
  seasons,
  selectedTeam,
  selectedSeason,
  onTeamChange,
  onSeasonChange,
  onReset,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredTeams, setFilteredTeams] = useState<Team[]>(teams);

  useEffect(() => {
    if (searchTerm) {
      setFilteredTeams(
        teams.filter((team) =>
          team.school.toLowerCase().includes(searchTerm.toLowerCase())
        )
      );
    } else {
      setFilteredTeams(teams);
    }
  }, [searchTerm, teams]);

  return (
    <div className="bg-white p-4 rounded-lg shadow-md mb-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Search Team
          </label>
          <input
            type="text"
            placeholder="Type to search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Team
          </label>
          <select
            value={selectedTeam}
            onChange={(e) => onTeamChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Teams</option>
            {filteredTeams.map((team) => (
              <option key={team.id} value={team.school}>
                {team.school}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Season
          </label>
          <select
            value={selectedSeason || ''}
            onChange={(e) => onSeasonChange(e.target.value ? Number(e.target.value) : undefined)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Seasons</option>
            {seasons.map((season) => (
              <option key={season.season} value={season.season}>
                {season.season} ({season.game_count} games)
              </option>
            ))}
          </select>
        </div>
      </div>

      {(selectedTeam || selectedSeason) && (
        <div className="mt-4">
          <button
            onClick={onReset}
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            Clear all filters
          </button>
        </div>
      )}
    </div>
  );
};

export default GameFilters;
