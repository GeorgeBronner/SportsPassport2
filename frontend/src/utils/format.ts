// Timezone used to render a game's calendar date. Real kickoff times
// (has_time=true) are stored as exact UTC instants — the API marks them
// explicitly as UTC (see naive_utc_isoformat on the backend), so `new
// Date(...)` parses the correct absolute instant on any client. Displaying
// with no explicit timeZone then falls back to the viewer's own local
// timezone, which is what most US evening games (CFB/NFL prime time,
// NBA/NHL/MLB night games) need: a game that kicks off after midnight UTC
// otherwise reads as the day *after* it actually happened.
//
// has_time=false rows (old bulk-imported data, e.g. Retrosheet MLB) only
// ever carry a naive midnight-UTC date with no real kickoff time attached,
// so they must stay pinned to UTC — reading them in the viewer's local
// timezone would roll them back a day instead.
export const displayTimeZone = (hasTime: boolean): string | undefined => (hasTime ? undefined : 'UTC');

// Format a game datetime as a readable date string, in the correct timezone
// for how it was stored (see displayTimeZone above).
export const formatDate = (isoDateString: string, hasTime = true): string => {
  const date = new Date(isoDateString);
  return date.toLocaleDateString('en-US', {
    timeZone: displayTimeZone(hasTime),
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
};

// Calendar year of a game date, in the correct timezone for how it was stored.
export const yearOf = (isoDateString: string, hasTime = true): number =>
  Number(
    new Intl.DateTimeFormat('en-US', { timeZone: displayTimeZone(hasTime), year: 'numeric' }).format(
      new Date(isoDateString)
    )
  );

// Short form of formatDate (e.g. "Jul 12, 2026")
export const formatDateShort = (isoDateString: string, hasTime = true): string => {
  const date = new Date(isoDateString);
  return date.toLocaleDateString('en-US', {
    timeZone: displayTimeZone(hasTime),
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
