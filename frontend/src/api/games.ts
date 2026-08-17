import apiClient from './client';
import type { GameListItem } from '../types/api';

export const gamesApi = {
  // Get all games for a specific team; attendedOnly = only games the caller
  // attended (server-side filter, not limited to the 100 most recent)
  getTeamGames: async (
    teamId: number,
    season?: number,
    attendedOnly?: boolean
  ): Promise<GameListItem[]> => {
    const params = new URLSearchParams();
    if (season) params.append('season', season.toString());
    if (attendedOnly) {
      params.append('attended_only', 'true');
      // Override the recency default — attended history must never truncate.
      params.append('limit', '1000');
    }

    const response = await apiClient.get<GameListItem[]>(`/games/team/${teamId}`, { params });
    return response.data;
  },
};
