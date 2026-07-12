import apiClient from './client';
import type { Game, GameListItem, SeasonInfo, GameFilters } from '../types/api';

export const gamesApi = {
  // Get all games with optional filters
  getGames: async (filters?: GameFilters): Promise<GameListItem[]> => {
    const params = new URLSearchParams();
    if (filters?.league) params.append('league', filters.league);
    if (filters?.season) params.append('season', filters.season.toString());
    if (filters?.team) params.append('team', filters.team);
    if (filters?.skip) params.append('skip', filters.skip.toString());
    if (filters?.limit) params.append('limit', filters.limit.toString());

    const response = await apiClient.get<GameListItem[]>('/games/', { params });
    return response.data;
  },

  // Get single game by ID
  getGame: async (id: number): Promise<Game> => {
    const response = await apiClient.get<Game>(`/games/${id}`);
    return response.data;
  },

  // Search games by team name
  searchGames: async (query: string, league?: string): Promise<GameListItem[]> => {
    const params: Record<string, string> = { q: query };
    if (league) params.league = league;
    const response = await apiClient.get<GameListItem[]>('/games/search/', { params });
    return response.data;
  },

  // Get available seasons with game counts
  getSeasons: async (league?: string): Promise<SeasonInfo[]> => {
    const params = new URLSearchParams();
    if (league) params.append('league', league);
    const response = await apiClient.get<SeasonInfo[]>('/games/seasons', { params });
    return response.data;
  },

  // Count games matching filters
  countGames: async (filters?: GameFilters): Promise<number> => {
    const params = new URLSearchParams();
    if (filters?.league) params.append('league', filters.league);
    if (filters?.season) params.append('season', filters.season.toString());
    if (filters?.team) params.append('team', filters.team);

    const response = await apiClient.get<{ count: number }>('/games/count', { params });
    return response.data.count;
  },

  // Get all games for a specific team
  getTeamGames: async (teamId: number, season?: number): Promise<GameListItem[]> => {
    const params = new URLSearchParams();
    if (season) params.append('season', season.toString());

    const response = await apiClient.get<GameListItem[]>(`/games/team/${teamId}`, { params });
    return response.data;
  },
};
