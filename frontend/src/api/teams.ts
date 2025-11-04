import apiClient from './client';
import type { Team, TeamFilters } from '../types/api';

export const teamsApi = {
  // Get all teams with optional filters
  getTeams: async (filters?: TeamFilters): Promise<Team[]> => {
    const params = new URLSearchParams();
    if (filters?.conference) params.append('conference', filters.conference);
    if (filters?.search) params.append('search', filters.search);

    const response = await apiClient.get<Team[]>('/teams/', { params });
    return response.data;
  },
};
