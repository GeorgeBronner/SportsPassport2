import React, { useState } from 'react';
import type { GameListItem } from '../../types/api';
import { formatDateShort, formatScore, formatGameWeek } from '../../utils/format';
import Card from '../common/Card';
import Button from '../common/Button';

interface GameCardProps {
  game: GameListItem;
  isAttended?: boolean;
  onAttend?: (gameId: number, notes?: string) => void;
  onRemoveAttendance?: (gameId: number) => void;
}

const GameCard: React.FC<GameCardProps> = ({
  game,
  isAttended = false,
  onAttend,
  onRemoveAttendance,
}) => {
  const [showNotesInput, setShowNotesInput] = useState(false);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);

  const handleAttend = async () => {
    if (!onAttend) return;
    setLoading(true);
    try {
      await onAttend(game.id, notes || undefined);
      setShowNotesInput(false);
      setNotes('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="hover:border-primary-300 bg-gradient-to-r from-white to-gray-50 relative">
      <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-6">
        <div className="flex-1">
          <div className="text-xs font-bold text-primary-600 mb-3 uppercase tracking-wider bg-primary-50 inline-block px-3 py-1 rounded-full">
            {formatDateShort(game.start_date)} • {formatGameWeek(game.week, game.season_type)}
          </div>
          <div className="text-2xl font-bold text-gray-900 mb-3">
            {game.away_team.school} @ {game.home_team.school}
          </div>
          <div className="text-lg text-gray-700 mb-3">
            <span className="font-semibold">Score:</span> <span className="text-accent-600 font-bold">{formatScore(game.away_score, game.home_score)}</span>
          </div>
          {game.venue && (
            <div className="text-sm text-gray-600 bg-sage-50 inline-block px-3 py-2 rounded-lg">
              <span className="inline-block mr-1">📍</span>
              <span className="font-medium">{game.venue.name}</span>
              {game.venue.city && game.venue.state && (
                <span> • {game.venue.city}, {game.venue.state}</span>
              )}
            </div>
          )}
        </div>

        <div className="flex-shrink-0 md:ml-4">
          {!isAttended ? (
            <div>
              {!showNotesInput ? (
                <Button size="sm" onClick={() => setShowNotesInput(true)}>
                  Mark Attended
                </Button>
              ) : (
                <div className="space-y-3">
                  <input
                    type="text"
                    placeholder="Add notes (optional)"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 w-full"
                  />
                  <div className="flex space-x-2">
                    <Button size="sm" onClick={handleAttend} disabled={loading}>
                      Save
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setShowNotesInput(false);
                        setNotes('');
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center">
              <span className="text-sm text-sage-600 font-bold bg-sage-50 px-4 py-2 rounded-lg">✓ Attended</span>
            </div>
          )}
        </div>
      </div>

      {/* Small undo button in bottom right corner when attended */}
      {isAttended && onRemoveAttendance && (
        <button
          onClick={() => onRemoveAttendance(game.id)}
          className="absolute bottom-2 right-2 text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1 hover:bg-red-50 rounded"
          title="Remove attendance"
        >
          undo
        </button>
      )}
    </Card>
  );
};

export default GameCard;
