import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { attendanceApi } from '../api/attendance';
import type { Attendance } from '../types/api';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import StampCard from '../components/passport/StampCard';
import TeamBadge from '../components/common/TeamBadge';
import { LEAGUE_ORDER, leagueColor } from '../utils/leagues';
import { formatDateShort } from '../utils/format';

const RECENT_STAMPS = 12;

/** The attendance log: recent entry stamps up top, full ledger below. */
const MyGames: React.FC = () => {
  const [attendedGames, setAttendedGames] = useState<Attendance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNotes, setEditNotes] = useState('');

  // Filters. 235 rows in one flat list had no way in at all — no league, no
  // season, no search — while Find and Map both offered league chips.
  const [league, setLeague] = useState('');
  const [season, setSeason] = useState<number | ''>('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    attendanceApi
      .getAttendedGames()
      .then((data) =>
        setAttendedGames(
          data.sort(
            (a, b) => new Date(b.game.start_date).getTime() - new Date(a.game.start_date).getTime()
          )
        )
      )
      .catch((err) => {
        console.error('Failed to load attended games', err);
        setError('Failed to load attended games');
      })
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: number) => {
    if (!confirm('Remove this game from your passport?')) return;
    try {
      await attendanceApi.deleteAttendance(id);
      setAttendedGames((current) => current.filter((a) => a.id !== id));
      setSuccess('Game removed');
      setTimeout(() => setSuccess(''), 3000);
    } catch {
      setError('Failed to remove game');
    }
  };

  const handleUpdateNotes = async (id: number) => {
    try {
      // Explicit null so blanking the input clears the saved note server-side.
      const updated = await attendanceApi.updateAttendance(id, {
        notes: editNotes.trim() || null,
      });
      setAttendedGames((current) =>
        current.map((a) => (a.id === id ? { ...a, notes: updated.notes } : a))
      );
      setEditingId(null);
      setEditNotes('');
      setSuccess('Notes updated');
      setTimeout(() => setSuccess(''), 3000);
    } catch {
      setError('Failed to update notes');
    }
  };

  const leaguesPresent = useMemo(
    () => new Set(attendedGames.map((a) => a.game.league.code)),
    [attendedGames]
  );

  const seasonsPresent = useMemo(
    () => [...new Set(attendedGames.map((a) => a.game.season))].sort((a, b) => b - a),
    [attendedGames]
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return attendedGames.filter(({ game, notes }) => {
      if (league && game.league.code !== league) return false;
      if (season !== '' && game.season !== season) return false;
      if (!q) return true;
      return [
        game.home_team.name,
        game.away_team.name,
        game.venue?.name,
        game.venue?.city,
        game.venue?.state,
        notes,
      ]
        .filter(Boolean)
        .some((field) => field!.toLowerCase().includes(q));
    });
  }, [attendedGames, league, season, query]);

  // Derived from the controls, not from the row count: a filter that happens
  // to match everything (one-league user clicking their only chip) is still an
  // active filter and still needs its Clear button.
  const filtered = league !== '' || season !== '' || query.trim() !== '';

  if (loading) return <Loading message="Loading your games..." />;

  return (
    <Layout>
      <div className="flex items-baseline gap-4 flex-wrap mb-6">
        <div>
          <p className="kicker">My log</p>
          <h1 className="text-2xl font-bold text-ink">
            {attendedGames.length} game{attendedGames.length !== 1 ? 's' : ''} attended
          </h1>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {attendedGames.length === 0 ? (
        <div className="bg-panel border border-line rounded-xl py-14 text-center">
          <p className="text-ink-2 mb-5">Your passport has no stamps yet.</p>
          <Link
            to="/"
            className="inline-block px-6 py-2.5 rounded-lg bg-focus text-white font-semibold text-sm"
          >
            Find your first game
          </Link>
        </div>
      ) : (
        <>
          <div className="bg-panel border border-line rounded-xl p-5 mb-4">
            <h2 className="kicker mb-2">Latest entry stamps</h2>
            {/* A genuine horizontal shelf rather than a hard six: six left ~40%
                of a wide monitor empty. overflow-y-hidden is explicit because
                `overflow-x: auto` would otherwise force both axes to scroll and
                clip the stamps' rotation. */}
            <div className="flex gap-7 items-center overflow-x-auto overflow-y-hidden py-3">
              {attendedGames.slice(0, RECENT_STAMPS).map((attendance, i) => (
                <StampCard key={attendance.id} attendance={attendance} index={i} />
              ))}
            </div>
          </div>

          <div className="bg-panel border border-line rounded-xl p-3 mb-3 flex gap-2 flex-wrap items-center">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search team, venue, note…"
              aria-label="Search your log"
              className="flex-1 min-w-44 text-sm px-3 py-1.5 rounded-lg bg-panel-2 text-ink border border-line placeholder:text-ink-3 focus:outline-2 focus:outline-focus"
            />
            <div className="flex gap-1.5 flex-wrap">
              {['', ...LEAGUE_ORDER.filter((c) => leaguesPresent.has(c))].map((code) => (
                <button
                  key={code || 'all'}
                  type="button"
                  onClick={() => setLeague(code)}
                  className={`text-[11px] uppercase tracking-[0.12em] px-3 py-1.5 rounded-full border transition-colors ${
                    league === code
                      ? 'border-line-strong bg-panel-2 text-ink font-bold'
                      : 'border-line text-ink-2 hover:text-ink'
                  }`}
                >
                  {code ? (
                    <>
                      <span
                        className="inline-block w-2 h-2 rounded-full mr-1.5"
                        style={{ backgroundColor: leagueColor(code) }}
                      />
                      {code}
                    </>
                  ) : (
                    'All'
                  )}
                </button>
              ))}
            </div>
            <select
              value={season}
              onChange={(e) => setSeason(e.target.value ? Number(e.target.value) : '')}
              aria-label="Season"
              className="text-xs bg-panel-2 text-ink border border-line rounded-lg px-2 py-1.5"
            >
              <option value="">All seasons</option>
              {seasonsPresent.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            <span className="text-xs text-ink-3 font-mono ml-auto">
              {visible.length} of {attendedGames.length}
            </span>
            {filtered && (
              <button
                type="button"
                onClick={() => {
                  setLeague('');
                  setSeason('');
                  setQuery('');
                }}
                className="text-xs text-ink-2 hover:text-ink border border-line hover:border-line-strong rounded-lg px-2.5 py-1.5"
              >
                Clear
              </button>
            )}
          </div>

          {visible.length === 0 ? (
            <div className="bg-panel border border-line rounded-xl py-12 text-center">
              <p className="text-ink-2">No games match those filters.</p>
            </div>
          ) : (
            <div className="bg-panel border border-line rounded-xl divide-y divide-[var(--line)]">
              {visible.map((attendance) => {
                const game = attendance.game;
                const played = game.home_score !== null && game.away_score !== null;
                const homeResult = !played
                  ? null
                  : game.home_score! > game.away_score!
                    ? 'W'
                    : game.home_score! < game.away_score!
                      ? 'L'
                      : 'T';
                return (
                  <div
                    key={attendance.id}
                    className="group px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-2 hover:bg-panel-2 transition-colors"
                  >
                    <span className="font-mono text-xs text-ink-2 w-24 shrink-0">
                      {formatDateShort(game.start_date, game.has_time)}
                    </span>
                    <span
                      className="text-[9px] font-extrabold tracking-[0.12em] uppercase text-white rounded px-1.5 py-0.5 shrink-0"
                      style={{ backgroundColor: leagueColor(game.league.code) }}
                    >
                      {game.league.code}
                    </span>
                    <span className="flex items-center gap-1.5 text-sm text-ink min-w-0">
                      <TeamBadge
                        name={game.away_team.name}
                        abbreviation={game.away_team.abbreviation}
                        logoUrl={game.away_team.logo_url}
                        leagueCode={game.league.code}
                        size="sm"
                      />
                      <Link to={`/teams/${game.away_team.id}`} className="hover:underline truncate">
                        {game.away_team.name}
                      </Link>
                      {game.away_score !== null && <b className="font-mono">{game.away_score}</b>}
                      <span className="text-ink-3">at</span>
                      <TeamBadge
                        name={game.home_team.name}
                        abbreviation={game.home_team.abbreviation}
                        logoUrl={game.home_team.logo_url}
                        leagueCode={game.league.code}
                        size="sm"
                      />
                      <Link to={`/teams/${game.home_team.id}`} className="hover:underline truncate">
                        {game.home_team.name}
                      </Link>
                      {game.home_score !== null && <b className="font-mono">{game.home_score}</b>}
                      {game.overtime_flag && (
                        <span className="text-[10px] font-mono text-ink-3">
                          {game.overtime_flag}
                        </span>
                      )}
                    </span>
                    {homeResult && (
                      <span
                        title={`Home team ${
                          homeResult === 'W' ? 'won' : homeResult === 'L' ? 'lost' : 'tied'
                        }`}
                        className={`inline-block w-[17px] h-[17px] rounded text-center leading-[17px] text-[9.5px] font-extrabold text-white shrink-0 ${
                          homeResult === 'W'
                            ? 'bg-win'
                            : homeResult === 'T'
                              ? 'bg-ink-3'
                              : 'bg-loss'
                        }`}
                      >
                        {homeResult}
                      </span>
                    )}
                    {game.venue && (
                      // The gutter used to end here with ~270px of nothing; the
                      // city and state were being truncated away instead.
                      <span className="text-xs text-ink-3 truncate">
                        {game.venue.name}
                        {game.venue.city ? ` · ${game.venue.city}` : ''}
                        {game.venue.state ? `, ${game.venue.state}` : ''}
                      </span>
                    )}
                    {game.neutral_site && (
                      <span className="text-[10px] uppercase tracking-[0.1em] text-ink-3 border border-line rounded px-1.5 shrink-0">
                        Neutral
                      </span>
                    )}
                    <span className="ml-auto flex items-center gap-2 shrink-0">
                      {attendance.notes && editingId !== attendance.id && (
                        <span className="text-xs text-ink-3" title="Has a note">
                          ✎
                        </span>
                      )}
                      {/* De-emphasised until hover/focus rather than hidden.
                          `Remove` is destructive and shouldn't shout on all 235
                          rows, but the two earlier attempts both broke: plain
                          `opacity-0` left an invisible yet clickable target, and
                          gating pointer-events on `group-hover` made the row
                          actions unreachable on touch, where there is no
                          reliable hover at all — and this is the only place
                          notes can be edited. Low opacity keeps them visible,
                          tappable and focusable everywhere. */}
                      <span className="flex gap-2 opacity-45 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(attendance.id);
                            setEditNotes(attendance.notes || '');
                          }}
                          className="text-xs text-ink-3 hover:text-ink border border-line hover:border-line-strong rounded px-2 py-1"
                        >
                          {attendance.notes ? 'Edit notes' : 'Add notes'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(attendance.id)}
                          className="text-xs text-loss border border-line hover:border-line-strong rounded px-2 py-1"
                        >
                          Remove
                        </button>
                      </span>
                    </span>

                    {editingId === attendance.id ? (
                      <div className="w-full">
                        <textarea
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg bg-panel-2 text-ink border border-line focus:outline-2 focus:outline-focus text-sm"
                          rows={2}
                          placeholder="Notes about this game — who you went with, what you'll remember…"
                        />
                        <div className="mt-2 flex gap-2">
                          <button
                            type="button"
                            onClick={() => handleUpdateNotes(attendance.id)}
                            className="text-xs font-semibold bg-focus text-white rounded px-3 py-1.5"
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setEditingId(null);
                              setEditNotes('');
                            }}
                            className="text-xs text-ink-2 border border-line rounded px-3 py-1.5"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      attendance.notes && (
                        <p
                          className="w-full text-[13px] italic font-serif text-ink-2 border-l-2 pl-3"
                          style={{ borderColor: 'var(--stamp)' }}
                        >
                          {attendance.notes}
                        </p>
                      )
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </Layout>
  );
};

export default MyGames;
