import React, { useState, useEffect } from 'react';
import { attendanceApi } from '../api/attendance';
import type { Attendance } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import { formatDateShort, formatScore } from '../utils/format';

const MyGames: React.FC = () => {
  const [attendedGames, setAttendedGames] = useState<Attendance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNotes, setEditNotes] = useState('');

  useEffect(() => {
    loadAttendedGames();
  }, []);

  const loadAttendedGames = async () => {
    setLoading(true);
    try {
      const data = await attendanceApi.getAttendedGames();
      setAttendedGames(data.sort((a, b) =>
        new Date(b.game.game_date).getTime() - new Date(a.game.game_date).getTime()
      ));
    } catch (err) {
      setError('Failed to load attended games');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to remove this game from your attended list?')) {
      return;
    }

    try {
      await attendanceApi.deleteAttendance(id);
      setAttendedGames(attendedGames.filter((a) => a.id !== id));
      setSuccess('Game removed from attended list');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to remove game');
    }
  };

  const handleUpdateNotes = async (id: number) => {
    try {
      await attendanceApi.updateAttendance(id, { notes: editNotes || undefined });
      setAttendedGames(
        attendedGames.map((a) =>
          a.id === id ? { ...a, notes: editNotes || null } : a
        )
      );
      setEditingId(null);
      setEditNotes('');
      setSuccess('Notes updated');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to update notes');
    }
  };

  const startEdit = (attendance: Attendance) => {
    setEditingId(attendance.id);
    setEditNotes(attendance.notes || '');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditNotes('');
  };

  if (loading) {
    return <Loading message="Loading your games..." />;
  }

  return (
    <Layout>
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-8">My Attended Games</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        {attendedGames.length === 0 ? (
          <Card className="bg-gradient-to-br from-accent-50 to-white">
            <div className="text-center py-12">
              <p className="text-gray-700 mb-6 text-lg">
                You haven't marked any games as attended yet.
              </p>
              <a href="/games" className="inline-block px-8 py-3 bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-all shadow-md hover:shadow-lg font-semibold">
                Browse games to get started
              </a>
            </div>
          </Card>
        ) : (
          <div>
            <p className="text-sm text-gray-700 mb-8 font-semibold uppercase tracking-wide">
              {attendedGames.length} game{attendedGames.length !== 1 ? 's' : ''} attended
            </p>
            <div className="space-y-6">
              {attendedGames.map((attendance) => (
                <Card key={attendance.id} className="bg-gradient-to-r from-white to-gray-50 hover:border-accent-300">
                  <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-6">
                    <div className="flex-1">
                      <div className="text-xs font-bold text-accent-600 mb-3 uppercase tracking-wider bg-accent-50 inline-block px-3 py-1 rounded-full">
                        {formatDateShort(attendance.game.game_date)} • Week {attendance.game.week || 'N/A'}
                      </div>
                      <div className="text-2xl font-bold text-gray-900 mb-3">
                        {attendance.game.away_team.school} @ {attendance.game.home_team.school}
                      </div>
                      <div className="text-lg text-gray-700 mb-3">
                        <span className="font-semibold">Score:</span> <span className="text-primary-600 font-bold">{formatScore(attendance.game.away_score, attendance.game.home_score)}</span>
                      </div>
                      {attendance.game.venue && (
                        <div className="text-sm text-gray-600 bg-sage-50 inline-block px-3 py-2 rounded-lg mb-4">
                          <span className="inline-block mr-1">📍</span>
                          <span className="font-medium">{attendance.game.venue.name}</span>
                          {attendance.game.venue.city && attendance.game.venue.state && (
                            <span> • {attendance.game.venue.city}, {attendance.game.venue.state}</span>
                          )}
                        </div>
                      )}

                      {editingId === attendance.id ? (
                        <div className="mt-4">
                          <textarea
                            value={editNotes}
                            onChange={(e) => setEditNotes(e.target.value)}
                            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                            rows={3}
                            placeholder="Add notes about this game..."
                          />
                          <div className="mt-3 flex space-x-2">
                            <Button size="sm" onClick={() => handleUpdateNotes(attendance.id)}>
                              Save
                            </Button>
                            <Button size="sm" variant="secondary" onClick={cancelEdit}>
                              Cancel
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <>
                          {attendance.notes && (
                            <div className="mt-3 p-4 bg-primary-50 rounded-xl border-l-4 border-primary-500">
                              <p className="text-sm text-gray-800 font-medium">{attendance.notes}</p>
                            </div>
                          )}
                        </>
                      )}
                    </div>

                    {editingId !== attendance.id && (
                      <div className="flex-shrink-0 md:ml-4 flex flex-col sm:flex-row gap-2">
                        <Button size="sm" variant="secondary" onClick={() => startEdit(attendance)}>
                          {attendance.notes ? 'Edit Notes' : 'Add Notes'}
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => handleDelete(attendance.id)}>
                          Remove
                        </Button>
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default MyGames;
