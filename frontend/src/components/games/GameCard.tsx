import React, { useState } from 'react';
import type { GameListItem } from '../../types/api';
import { formatDateShort, formatScore } from '../../utils/format';
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
    <Card className="hover:shadow-xl transition-all duration-200 hover:border-blue-300">
      <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4">
        <div className="flex-1">
          <div className="text-xs font-medium text-blue-600 mb-2 uppercase tracking-wide">
            {formatDateShort(game.game_date)} • Week {game.week || 'N/A'}
          </div>
          <div className="text-xl font-bold text-gray-900 mb-2">
            {game.away_team.school} @ {game.home_team.school}
          </div>
          <div className="text-base text-gray-600 mb-3">
            <span className="font-semibold">Score:</span> {formatScore(game.away_score, game.home_score)}
          </div>
          {game.venue && (
            <div className="text-sm text-gray-500">
              <span className="inline-block mr-1">📍</span>
              {game.venue.name}
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
                <div className="space-y-2">
                  <input
                    type="text"
                    placeholder="Add notes (optional)"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="px-2 py-1 text-sm border border-gray-300 rounded"
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
            <div className="flex items-center space-x-2">
              <span className="text-sm text-green-600 font-medium">✓ Attended</span>
              {onRemoveAttendance && (
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => onRemoveAttendance(game.id)}
                >
                  Remove
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};

export default GameCard;
