// Format date to readable string
export const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
};

// Format date to short form
export const formatDateShort = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
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
