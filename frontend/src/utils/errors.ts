import { isAxiosError } from 'axios';

/**
 * The human-readable message for a failed API call.
 *
 * FastAPI puts its message in the response body's `detail`. Anything else —
 * a network failure, a non-Axios throw, a body without `detail` — has nothing
 * worth showing a user, so the caller's fallback wins.
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
  }
  return fallback;
}
