import apiClient from './client';
import type { User, ImportResult, AdminStatusRow } from '../types/api';

export const adminApi = {
  // Import/refresh teams for a league
  importTeams: async (league: string): Promise<ImportResult> => {
    const response = await apiClient.post<ImportResult>(`/admin/import/${league}/teams`);
    return response.data;
  },

  // One-time bulk historical import for a league
  importHistorical: async (
    league: string,
    startSeason: number,
    endSeason: number
  ): Promise<ImportResult> => {
    const response = await apiClient.post<ImportResult>(
      `/admin/import/${league}/historical`,
      null,
      { params: { start_season: startSeason, end_season: endSeason } }
    );
    return response.data;
  },

  // Incremental sync of recent games for a league
  syncLeague: async (league: string, days: number = 7): Promise<ImportResult> => {
    const response = await apiClient.post<ImportResult>(`/admin/sync/${league}`, null, {
      params: { days },
    });
    return response.data;
  },

  // Run the nightly sync on demand across every enabled league
  syncAll: async (): Promise<ImportResult[]> => {
    const response = await apiClient.post<ImportResult[]>('/admin/sync-all');
    return response.data;
  },

  // Enable/disable a league in the nightly auto-sync
  setSyncEnabled: async (league: string, enabled: boolean): Promise<{ league: string; enabled: boolean }> => {
    const response = await apiClient.patch<{ league: string; enabled: boolean }>(
      `/admin/sync-state/${league}`,
      { enabled }
    );
    return response.data;
  },

  // Per-league row counts and season coverage
  getStatus: async (): Promise<AdminStatusRow[]> => {
    const response = await apiClient.get<AdminStatusRow[]>('/admin/status');
    return response.data;
  },

  // Get all users (admin only)
  getUsers: async (): Promise<User[]> => {
    const response = await apiClient.get<User[]>('/admin/users');
    return response.data;
  },

  // Promote user to admin
  promoteUser: async (userId: number): Promise<User> => {
    const response = await apiClient.post<User>(`/admin/users/${userId}/promote`);
    return response.data;
  },

  // Demote user from admin
  demoteUser: async (userId: number): Promise<User> => {
    const response = await apiClient.post<User>(`/admin/users/${userId}/demote`);
    return response.data;
  },
};
