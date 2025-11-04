import apiClient from './client';
import type {
  Attendance,
  AttendanceCreate,
  AttendanceUpdate,
  AttendanceStats,
  BulkAttendanceRequest,
  BulkAttendanceResponse,
} from '../types/api';

export const attendanceApi = {
  // Mark a game as attended
  createAttendance: async (data: AttendanceCreate): Promise<Attendance> => {
    const response = await apiClient.post<Attendance>('/attendance/', data);
    return response.data;
  },

  // Mark multiple games as attended
  bulkCreateAttendance: async (data: BulkAttendanceRequest): Promise<BulkAttendanceResponse> => {
    const response = await apiClient.post<BulkAttendanceResponse>('/attendance/bulk', data);
    return response.data;
  },

  // Get user's attended games
  getAttendedGames: async (): Promise<Attendance[]> => {
    const response = await apiClient.get<Attendance[]>('/attendance/');
    return response.data;
  },

  // Get attendance statistics
  getStats: async (): Promise<AttendanceStats> => {
    const response = await apiClient.get<AttendanceStats>('/attendance/stats');
    return response.data;
  },

  // Update attendance notes
  updateAttendance: async (id: number, data: AttendanceUpdate): Promise<Attendance> => {
    const response = await apiClient.patch<Attendance>(`/attendance/${id}`, data);
    return response.data;
  },

  // Delete attendance record
  deleteAttendance: async (id: number): Promise<void> => {
    await apiClient.delete(`/attendance/${id}`);
  },
};
