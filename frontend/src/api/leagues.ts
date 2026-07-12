import apiClient from './client';
import type { League } from '../types/api';

export const leaguesApi = {
  // Get all leagues
  getLeagues: async (): Promise<League[]> => {
    const response = await apiClient.get<League[]>('/leagues/');
    return response.data;
  },
};
