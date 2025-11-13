// Convert UTC datetime to Central Time and format as readable string
export const formatDate = (isoDateString: string): string => {
  const date = new Date(isoDateString);
  return date.toLocaleDateString('en-US', {
    timeZone: 'America/Chicago',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
};

// Convert UTC datetime to Central Time and format as short form
export const formatDateShort = (isoDateString: string): string => {
  const date = new Date(isoDateString);
  return date.toLocaleDateString('en-US', {
    timeZone: 'America/Chicago',
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

// Format game week or type (Bowl Game for postseason)
export const formatGameWeek = (week: number | null, seasonType: string | null): string => {
  if (seasonType === 'postseason') {
    return 'Bowl Game';
  }
  return week ? `Week ${week}` : 'N/A';
};
