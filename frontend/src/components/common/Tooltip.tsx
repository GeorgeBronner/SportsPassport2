import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { TooltipState } from '../../hooks/useTooltip';

/**
 * Renders the hover card for a `useTooltip()` state. Mount once per view.
 *
 * Portalled to `document.body` so it can never be clipped by an
 * `overflow:hidden` panel or trapped beneath a stacking context — the map's
 * old inline tooltip lived inside the map panel and was subject to both.
 */
const Tooltip: React.FC<{ tip: TooltipState | null }> = ({ tip }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  // Measured after paint so the card can flip when it would overflow the
  // viewport — a tooltip that runs off-screen is worse than no tooltip.
  useEffect(() => {
    if (!tip || !ref.current) {
      setPos(null);
      return;
    }
    const { width, height } = ref.current.getBoundingClientRect();
    const left = tip.x + width + 22 > window.innerWidth ? tip.x - width - 14 : tip.x + 16;
    const top = tip.y - height - 12 < 8 ? tip.y + 20 : tip.y - height - 12;
    setPos({ left, top });
  }, [tip]);

  if (!tip) return null;

  return createPortal(
    <div
      ref={ref}
      role="tooltip"
      className="fixed z-[60] pointer-events-none bg-panel border border-line-strong rounded-lg px-3 py-2 shadow-elevated max-w-64"
      // Off-screen for the first frame, then positioned from the measurement
      // above — avoids a visible jump when the card flips.
      style={pos ?? { left: -9999, top: -9999 }}
    >
      <div
        className="text-[13px] font-bold text-ink leading-tight"
        style={tip.color ? { color: tip.color } : undefined}
      >
        {tip.title}
      </div>
      {tip.lines?.filter(Boolean).map((line) => (
        <div key={line} className="text-[11.5px] text-ink-2 leading-snug mt-0.5">
          {line}
        </div>
      ))}
    </div>,
    document.body
  );
};

export default Tooltip;
