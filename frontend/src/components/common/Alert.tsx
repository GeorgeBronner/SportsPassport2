import React from 'react';

interface AlertProps {
  type?: 'info' | 'success' | 'warning' | 'error';
  message: string;
  onClose?: () => void;
}

/** Token-based so it reads correctly on the dark pages that render it —
 *  the previous fixed `bg-*-50` tints were near-white slabs in dark mode. */
const ACCENTS: Record<NonNullable<AlertProps['type']>, string> = {
  info: 'var(--focus)',
  success: 'var(--win)',
  warning: 'var(--lg-nba)',
  error: 'var(--loss)',
};

const Alert: React.FC<AlertProps> = ({ type = 'info', message, onClose }) => {
  const accent = ACCENTS[type];

  return (
    <div
      role={type === 'error' ? 'alert' : 'status'}
      className="border border-line border-l-4 rounded-lg px-4 py-3 mb-4 bg-panel"
      style={{
        borderLeftColor: accent,
        // 8% of the accent over the panel keeps the tint readable in both
        // themes without hard-coding a light and a dark variant.
        backgroundColor: `color-mix(in srgb, ${accent} 8%, var(--panel))`,
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-ink font-medium">{message}</p>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Dismiss"
            className="text-ink-3 hover:text-ink transition-colors font-bold text-lg leading-none shrink-0"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
};

export default Alert;
