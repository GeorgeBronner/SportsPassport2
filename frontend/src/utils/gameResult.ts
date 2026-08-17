export type GameResult = 'W' | 'L' | 'T';

/** Win/loss/tie from one side's perspective — null until both scores are in. */
export const getGameResult = (
  myScore: number | null,
  oppScore: number | null
): GameResult | null => {
  if (myScore === null || oppScore === null) return null;
  if (myScore > oppScore) return 'W';
  if (myScore < oppScore) return 'L';
  return 'T';
};
