import { useCallback, useEffect, useState } from 'react';

type Theme = 'light' | 'dark';

const stored = (): Theme | null => {
  const v = localStorage.getItem('theme');
  return v === 'light' || v === 'dark' ? v : null;
};

const systemTheme = (): Theme =>
  window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

/** Current theme with an explicit toggle; the choice persists and overrides the OS. */
export const useTheme = () => {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? systemTheme());

  useEffect(() => {
    // Only stamp data-theme when the user has made an explicit choice, so
    // un-toggled visitors keep following their OS preference live.
    if (stored()) {
      document.documentElement.dataset.theme = theme;
    }
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      document.documentElement.dataset.theme = next;
      return next;
    });
  }, []);

  return { theme, toggle };
};
