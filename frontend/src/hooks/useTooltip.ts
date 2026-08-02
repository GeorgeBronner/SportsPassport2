import { useCallback, useState } from 'react';
import type React from 'react';

export interface TooltipContent {
  title: string;
  lines?: string[];
  /** Accent applied to the title — league colour, usually. */
  color?: string;
}

export interface TooltipState extends TooltipContent {
  x: number;
  y: number;
}

/**
 * Imperative handle shared by everything that wants a styled hover card.
 *
 * Native `title=` was doing this job across the app: ~1s delay, unstyleable,
 * and invisible on touch. Pair with `<Tooltip tip={tip} />` once per view.
 */
export const useTooltip = () => {
  const [tip, setTip] = useState<TooltipState | null>(null);

  const show = useCallback((e: { clientX: number; clientY: number }, content: TooltipContent) => {
    setTip({ ...content, x: e.clientX, y: e.clientY });
  }, []);
  const hide = useCallback(() => setTip(null), []);

  /** Spread onto any element to give it a tooltip. Both enter and move are
   *  bound: a synthetic or stationary pointer never fires `mousemove`, so
   *  binding move alone leaves the tooltip permanently hidden — which is
   *  exactly what the map's venue dots used to do. */
  const bind = useCallback(
    (content: TooltipContent) => ({
      onMouseEnter: (e: React.MouseEvent) => show(e, content),
      onMouseMove: (e: React.MouseEvent) => show(e, content),
      onMouseLeave: hide,
    }),
    [show, hide]
  );

  return { tip, show, hide, bind };
};
