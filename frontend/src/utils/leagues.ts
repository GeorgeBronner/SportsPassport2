// Fixed league display order and color slots (colorblind-validated palette).
// Colors resolve through CSS vars so light/dark variants swap automatically.

export const LEAGUE_ORDER = ['CFB', 'MLB', 'NFL', 'NBA', 'NHL', 'CBB', 'MLS'] as const;

export type LeagueCode = (typeof LEAGUE_ORDER)[number];

export const leagueColor = (code: string): string =>
  `var(--lg-${code.toLowerCase()}, var(--ink-3))`;

export const sortByLeagueOrder = (a: string, b: string): number => {
  const ia = LEAGUE_ORDER.indexOf(a as LeagueCode);
  const ib = LEAGUE_ORDER.indexOf(b as LeagueCode);
  return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
};
