// Format a UTC datetime as a readable date string. Formatted in UTC, not a
// fixed US timezone: many historical rows (e.g. Retrosheet-sourced MLB games)
// store start_date as a naive midnight-UTC date, and converting that to any
// non-UTC timezone rolls the displayed date back a day. The app never shows
// time-of-day, only the calendar date, so UTC is the safe default across
// every league rather than a CFB-specific approximation.
export const formatDate = (isoDateString: string): string => {
  const date = new Date(isoDateString);
  return date.toLocaleDateString('en-US', {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
};

// Short form of formatDate (e.g. "Jul 12, 2026")
export const formatDateShort = (isoDateString: string): string => {
  const date = new Date(isoDateString);
  return date.toLocaleDateString('en-US', {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

// Format team matchup (e.g., "Michigan vs Ohio State")
export const formatMatchup = (homeTeam: string, awayTeam: string): string => {
  return `${awayTeam} @ ${homeTeam}`;
};

// Format score (e.g., "42-27")
export const formatScore = (awayScore: number | null, homeScore: number | null): string => {
  if (awayScore === null || homeScore === null) {
    return 'TBD';
  }
  return `${awayScore}-${homeScore}`;
};

// Get winner from scores
export const getWinner = (
  homeTeam: string,
  awayTeam: string,
  homeScore: number | null,
  awayScore: number | null
): string | null => {
  if (homeScore === null || awayScore === null) {
    return null;
  }
  if (homeScore > awayScore) {
    return homeTeam;
  } else if (awayScore > homeScore) {
    return awayTeam;
  }
  return 'Tie';
};

const SEASON_TYPE_LABELS: Record<string, string> = {
  postseason: 'Postseason',
  preseason: 'Preseason',
  cup_final: 'Cup Final',
  regular: 'Regular Season',
};

// Format game week or season type (e.g. "Week 5", "Postseason", "Cup Final").
// Not every league has a week number (only CFB/NFL do), so this falls back
// to a season-type label shared across all leagues.
export const formatSeasonType = (week: number | null, seasonType: string | null): string => {
  if (week) {
    return `Week ${week}`;
  }
  return SEASON_TYPE_LABELS[seasonType ?? ''] ?? 'Regular Season';
};
