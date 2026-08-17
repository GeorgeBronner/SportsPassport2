import apiClient from './client';
import type { Team, TeamSearchResult, TeamAttendanceStats } from '../types/api';

export const teamsApi = {
  // Get single team by ID
  getTeam: async (id: number): Promise<Team> => {
    const response = await apiClient.get<Team>(`/teams/${id}`);
    return response.data;
  },

  // Cross-league team search for the omnibox
  searchTeams: async (q: string, league?: string, limit = 20): Promise<TeamSearchResult[]> => {
    const params: Record<string, string> = { q, limit: String(limit) };
    if (league) params.league = league;
    const response = await apiClient.get<TeamSearchResult[]>('/teams/search', { params });
    return response.data;
  },

  // Current user's history with one team
  getAttendanceStats: async (id: number): Promise<TeamAttendanceStats> => {
    const response = await apiClient.get<TeamAttendanceStats>(`/teams/${id}/attendance-stats`);
    return response.data;
  },
};
