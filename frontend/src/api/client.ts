import axios from 'axios';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Endpoints where a 401 is an expected outcome (bad credentials / wrong current
// password) and must be handled by the calling component, not trigger a
// global logout-and-redirect.
const AUTH_ENDPOINTS = ['/auth/login', '/auth/password'];

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || '';
    const isAuthEndpoint = AUTH_ENDPOINTS.some((path) => url.includes(path));
    if (error.response?.status === 401 && !isAuthEndpoint) {
      // Token expired or invalid, clear storage and redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
