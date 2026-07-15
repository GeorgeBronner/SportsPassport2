import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { teamsApi } from '../../api/teams';
import type { TeamSearchResult } from '../../types/api';
import { LEAGUE_ORDER, leagueColor, sortByLeagueOrder } from '../../utils/leagues';
import TeamBadge from '../common/TeamBadge';

interface OmniboxProps {
  onSelect: (team: TeamSearchResult) => void;
  autoFocus?: boolean;
  placeholder?: string;
  /** Controlled league filter; omit to let the omnibox manage it internally. */
  league?: string;
  /** Fires on league-tab clicks. queryEmpty lets callers treat a click with
   *  nothing typed as navigation instead of a search filter. */
  onLeagueChange?: (code: string, queryEmpty: boolean) => void;
}

/** Cross-league team finder: debounced typeahead, league tabs, keyboard nav. */
const Omnibox: React.FC<OmniboxProps> = ({
  onSelect,
  autoFocus,
  placeholder,
  league: leagueProp,
  onLeagueChange,
}) => {
  const [q, setQ] = useState('');
  const [internalLeague, setInternalLeague] = useState('');
  const league = leagueProp !== undefined ? leagueProp : internalLeague;

  const selectLeague = (code: string) => {
    if (leagueProp === undefined) setInternalLeague(code);
    onLeagueChange?.(code, q.trim().length === 0);
  };
  const [results, setResults] = useState<TeamSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const listboxId = useId();
  const boxRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<number | undefined>(undefined);
  // Generation counter so a slow response for an old query/league can't
  // overwrite the results of a newer one.
  const requestRef = useRef(0);

  useEffect(() => {
    const requestId = ++requestRef.current;
    window.clearTimeout(debounceRef.current);
    if (q.trim().length < 2) {
      setResults([]);
      setOpen(false);
      setLoading(false);
      return;
    }
    debounceRef.current = window.setTimeout(async () => {
      setLoading(true);
      try {
        const data = await teamsApi.searchTeams(q.trim(), league || undefined);
        if (requestId !== requestRef.current) return;
        setResults(data);
        setOpen(true);
        setActive(-1);
      } catch {
        if (requestId !== requestRef.current) return;
        setResults([]);
      } finally {
        if (requestId === requestRef.current) setLoading(false);
      }
    }, 200);
    return () => window.clearTimeout(debounceRef.current);
  }, [q, league]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const grouped = useMemo(() => {
    const byLeague = new Map<string, TeamSearchResult[]>();
    for (const r of results) {
      const list = byLeague.get(r.league_code) ?? [];
      list.push(r);
      byLeague.set(r.league_code, list);
    }
    return [...byLeague.entries()].sort(([a], [b]) => sortByLeagueOrder(a, b));
  }, [results]);

  // Flat list in display order, for keyboard navigation
  const flat = useMemo(() => grouped.flatMap(([, teams]) => teams), [grouped]);
  const indexById = useMemo(
    () => new Map(flat.map((t, i) => [t.id, i] as [number, number])),
    [flat]
  );

  const pick = (team: TeamSearchResult) => {
    setOpen(false);
    setQ('');
    onSelect(team);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open || flat.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, flat.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault();
      pick(flat[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div ref={boxRef} className="relative">
      <input
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={
          open && active >= 0 && flat[active] ? `${listboxId}-${flat[active].id}` : undefined
        }
        aria-label="Find a team"
        autoFocus={autoFocus}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => q.trim().length >= 2 && setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder ?? 'Find a team, any league…'}
        className="w-full text-lg md:text-xl px-4 py-3.5 rounded-xl bg-panel text-ink border border-line-strong placeholder:text-ink-3 focus:outline-2 focus:outline-focus"
        autoComplete="off"
      />

      <div className="flex flex-wrap gap-1.5 mt-2.5">
        {['', ...LEAGUE_ORDER].map((code) => (
          <button
            key={code || 'all'}
            type="button"
            onClick={() => selectLeague(code)}
            className={`text-[11px] uppercase tracking-[0.14em] px-3 py-1.5 rounded-md border transition-colors ${
              league === code
                ? 'border-line-strong bg-panel text-ink font-bold'
                : 'border-line text-ink-2 hover:text-ink'
            }`}
          >
            {code ? (
              <>
                <span
                  className="inline-block w-2 h-2 rounded-[2px] mr-1.5 align-[1px]"
                  style={{ backgroundColor: leagueColor(code) }}
                />
                {code}
              </>
            ) : (
              'All leagues'
            )}
          </button>
        ))}
      </div>

      {open && (
        <div
          role="listbox"
          id={listboxId}
          aria-label="Team results"
          className="absolute z-20 left-0 right-0 top-full mt-1.5 max-h-96 overflow-y-auto rounded-xl bg-panel border border-line-strong shadow-elevated"
        >
          {flat.length === 0 ? (
            <div className="p-4 text-ink-3 text-sm">
              {loading ? 'Searching…' : `No teams match “${q}”${league ? ` in ${league}` : ''}.`}
            </div>
          ) : (
            grouped.map(([code, teams]) => (
              <div key={code}>
                <div className="px-4 pt-2.5 pb-1 text-[10px] uppercase tracking-[0.2em] text-ink-3 border-t border-line first:border-t-0">
                  {code}
                </div>
                {teams.map((team) => {
                  const idx = indexById.get(team.id) ?? -1;
                  return (
                    <button
                      key={team.id}
                      type="button"
                      role="option"
                      id={`${listboxId}-${team.id}`}
                      aria-selected={idx === active}
                      onClick={() => pick(team)}
                      onMouseEnter={() => setActive(idx)}
                      className={`flex items-center gap-3 w-full text-left px-4 py-2.5 ${
                        idx === active ? 'bg-panel-2' : ''
                      }`}
                    >
                      <TeamBadge
                        name={team.name}
                        abbreviation={team.abbreviation}
                        logoUrl={team.logo_url}
                        leagueCode={team.league_code}
                        size="md"
                      />
                      <span className="text-ink">
                        {team.name}{' '}
                        {team.nickname && team.nickname !== team.name && (
                          <span className="text-ink-3">{team.nickname}</span>
                        )}
                      </span>
                      <span className="ml-auto text-xs text-ink-3 whitespace-nowrap">
                        {team.attended_count > 0 ? (
                          <>
                            <b className="text-ink">{team.attended_count}</b> attended
                          </>
                        ) : (
                          'none attended'
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default Omnibox;
