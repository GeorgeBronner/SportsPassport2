import { useCallback, useEffect, useRef, useState } from 'react';

const DEFAULT_TIMEOUT_MS = 3000;

/**
 * A message that clears itself after a delay — the
 * `setSuccess(x); setTimeout(() => setSuccess(''), 3000)` pattern repeated at
 * every "quick action" success toast. Cancels its timer on unmount/re-show,
 * so navigating away inside the window can't call setState on an unmounted
 * component. `setMessage` is exposed for callers that want to set text
 * without the auto-dismiss (a longer-running action whose result should
 * stick until the next one).
 */
export const useTimedMessage = (timeoutMs = DEFAULT_TIMEOUT_MS) => {
  const [message, setMessage] = useState('');
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const show = useCallback(
    (text: string) => {
      clearTimer();
      setMessage(text);
      timeoutRef.current = setTimeout(() => setMessage(''), timeoutMs);
    },
    [clearTimer, timeoutMs]
  );

  const dismiss = useCallback(() => {
    clearTimer();
    setMessage('');
  }, [clearTimer]);

  // A persistent set must win over a still-running timer from an earlier
  // show() — otherwise a timed toast followed within its window by a
  // persistent one gets silently wiped when the stale timer fires.
  const setPersistentMessage = useCallback(
    (text: string) => {
      clearTimer();
      setMessage(text);
    },
    [clearTimer]
  );

  useEffect(() => clearTimer, [clearTimer]);

  return { message, setMessage: setPersistentMessage, show, dismiss } as const;
};
