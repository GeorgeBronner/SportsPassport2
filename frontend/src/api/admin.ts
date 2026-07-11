import apiClient from './client';
import type { User } from '../types/api';

export const adminApi = {
  // Refresh data from API for a specific season
  refreshData: async (season: number): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(
      '/admin/refresh-data',
      null,
      { params: { season } }
    );
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
