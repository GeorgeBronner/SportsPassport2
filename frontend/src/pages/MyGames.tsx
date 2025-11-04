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
        <h1 className="text-3xl font-bold text-gray-900 mb-6">My Attended Games</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        {attendedGames.length === 0 ? (
          <Card>
            <div className="text-center py-8">
              <p className="text-gray-600 mb-4">
                You haven't marked any games as attended yet.
              </p>
              <a href="/games" className="text-blue-600 hover:text-blue-700">
                Browse games to get started
              </a>
            </div>
          </Card>
        ) : (
          <div>
            <p className="text-sm text-gray-600 mb-6 font-medium">
              {attendedGames.length} game{attendedGames.length !== 1 ? 's' : ''} attended
            </p>
            <div className="space-y-6">
              {attendedGames.map((attendance) => (
                <Card key={attendance.id} className="hover:shadow-xl transition-all duration-200">
                  <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4">
                    <div className="flex-1">
                      <div className="text-xs font-medium text-blue-600 mb-2 uppercase tracking-wide">
                        {formatDateShort(attendance.game.game_date)} • Week {attendance.game.week || 'N/A'}
                      </div>
                      <div className="text-xl font-bold text-gray-900 mb-2">
                        {attendance.game.away_team.school} @ {attendance.game.home_team.school}
                      </div>
                      <div className="text-base text-gray-600 mb-3">
                        <span className="font-semibold">Score:</span> {formatScore(attendance.game.away_score, attendance.game.home_score)}
                      </div>
                      {attendance.game.venue && (
                        <div className="text-sm text-gray-500 mb-3">
                          <span className="inline-block mr-1">📍</span>
                          {attendance.game.venue.name}
                          {attendance.game.venue.city && attendance.game.venue.state && (
                            <span> • {attendance.game.venue.city}, {attendance.game.venue.state}</span>
                          )}
                        </div>
                      )}

                      {editingId === attendance.id ? (
                        <div className="mt-3">
                          <textarea
                            value={editNotes}
                            onChange={(e) => setEditNotes(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            rows={3}
                            placeholder="Add notes about this game..."
                          />
                          <div className="mt-2 flex space-x-2">
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
                            <div className="mt-2 p-3 bg-gray-50 rounded-lg">
                              <p className="text-sm text-gray-700">{attendance.notes}</p>
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
