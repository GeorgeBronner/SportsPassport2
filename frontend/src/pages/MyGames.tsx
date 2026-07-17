import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { attendanceApi } from '../api/attendance';
import type { Attendance } from '../types/api';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import StampCard from '../components/passport/StampCard';
import TeamBadge from '../components/common/TeamBadge';
import { leagueColor } from '../utils/leagues';
import { formatDateShort } from '../utils/format';

/** The attendance log: recent entry stamps up top, full ledger below. */
const MyGames: React.FC = () => {
  const [attendedGames, setAttendedGames] = useState<Attendance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNotes, setEditNotes] = useState('');

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
      .catch(() => setError('Failed to load attended games'))
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
          <div className="bg-panel border border-line rounded-xl p-5 mb-4 overflow-x-auto">
            <h2 className="kicker mb-4">Latest entry stamps</h2>
            <div className="flex gap-7 items-center pb-1">
              {attendedGames.slice(0, 6).map((attendance, i) => (
                <StampCard key={attendance.id} attendance={attendance} index={i} />
              ))}
            </div>
          </div>

          <div className="bg-panel border border-line rounded-xl divide-y divide-[var(--line)]">
            {attendedGames.map((attendance) => {
              const game = attendance.game;
              return (
                <div key={attendance.id} className="px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
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
                      <span className="text-[10px] font-mono text-ink-3">{game.overtime_flag}</span>
                    )}
                  </span>
                  {game.venue && (
                    <span className="text-xs text-ink-3 truncate">
                      {game.venue.name}
                      {game.venue.city ? ` · ${game.venue.city}` : ''}
                    </span>
                  )}
                  <span className="ml-auto flex items-center gap-2 shrink-0">
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
                      <p className="w-full text-[13px] italic font-serif text-ink-2 border-l-2 pl-3" style={{ borderColor: 'var(--stamp)' }}>
                        {attendance.notes}
                      </p>
                    )
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </Layout>
  );
};

export default MyGames;
