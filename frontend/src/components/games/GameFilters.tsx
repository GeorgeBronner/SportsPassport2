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
    <div className="card-elevated p-6 mb-8 bg-gradient-to-br from-white to-primary-50 border-primary-100">
      <h3 className="text-lg font-bold text-gray-900 mb-5">Filter Games</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2 uppercase tracking-wide">
            Search Team
          </label>
          <input
            type="text"
            placeholder="Type to search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2 uppercase tracking-wide">
            Team
          </label>
          <select
            value={selectedTeam}
            onChange={(e) => onTeamChange(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
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
          <label className="block text-sm font-bold text-gray-700 mb-2 uppercase tracking-wide">
            Season
          </label>
          <select
            value={selectedSeason || ''}
            onChange={(e) => onSeasonChange(e.target.value ? Number(e.target.value) : undefined)}
            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
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
        <div className="mt-6">
          <button
            onClick={onReset}
            className="text-sm font-semibold text-accent-600 hover:text-accent-700 transition-colors"
          >
            Clear all filters
          </button>
        </div>
      )}
    </div>
  );
};

export default GameFilters;
