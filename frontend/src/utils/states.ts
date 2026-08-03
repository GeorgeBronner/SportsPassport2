/** US state name ↔ 2-letter code, shared by every view that groups by state.
 *
 * `venues.state` is a 2-letter code everywhere (see CLAUDE.md), so the lookup
 * exists for the *other* direction: the Census topology behind the map labels
 * its geometries by full name, and the tile map has always accepted either.
 */

export const STATE_NAME_TO_CODE: Record<string, string> = {
  alabama: 'AL', alaska: 'AK', arizona: 'AZ', arkansas: 'AR', california: 'CA',
  colorado: 'CO', connecticut: 'CT', delaware: 'DE', 'district of columbia': 'DC',
  florida: 'FL', georgia: 'GA', hawaii: 'HI', idaho: 'ID', illinois: 'IL',
  indiana: 'IN', iowa: 'IA', kansas: 'KS', kentucky: 'KY', louisiana: 'LA',
  maine: 'ME', maryland: 'MD', massachusetts: 'MA', michigan: 'MI',
  minnesota: 'MN', mississippi: 'MS', missouri: 'MO', montana: 'MT',
  nebraska: 'NE', nevada: 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
  'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
  'north dakota': 'ND', ohio: 'OH', oklahoma: 'OK', oregon: 'OR',
  pennsylvania: 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
  'south dakota': 'SD', tennessee: 'TN', texas: 'TX', utah: 'UT',
  vermont: 'VT', virginia: 'VA', washington: 'WA', 'west virginia': 'WV',
  wisconsin: 'WI', wyoming: 'WY',
};

/** Normalize either form to a 2-letter code. Unknown input is upper-cased and
 *  returned as-is, so an unexpected value still groups with itself rather than
 *  silently collapsing into another state's bucket. */
export const toStateCode = (state: string): string => {
  const s = state.trim();
  return s.length === 2
    ? s.toUpperCase()
    : (STATE_NAME_TO_CODE[s.toLowerCase()] ?? s.toUpperCase());
};

/** Sum a `{state: count}` map into 2-letter-code buckets. */
export const countsByStateCode = (
  gamesByState: Record<string, number>
): Record<string, number> => {
  const counts: Record<string, number> = {};
  for (const [state, count] of Object.entries(gamesByState)) {
    const code = toStateCode(state);
    counts[code] = (counts[code] ?? 0) + count;
  }
  return counts;
};
