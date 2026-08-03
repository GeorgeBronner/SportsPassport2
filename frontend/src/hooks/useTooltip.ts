import { useCallback, useEffect, useState } from 'react';
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

/** One-line form of the card, for the accessible name. */
const describe = ({ title, lines }: TooltipContent): string =>
  [title, ...(lines ?? []).filter(Boolean)].join(' — ');

/**
 * Imperative handle shared by everything that wants a styled hover card.
 *
 * Replaces native `title=` across the app (~1s delay, unstyleable). Because
 * that swap could easily have made things *less* reachable than the thing it
 * replaced, `bind()` deliberately covers three paths, not just the mouse:
 *
 *  - **mouse** — enter and move. Move alone is not enough: a synthetic or
 *    perfectly stationary pointer never fires `mousemove`, which is exactly
 *    why the map's old venue tooltip showed nothing until you jiggled.
 *  - **keyboard and touch** — focus/blur, plus Escape to dismiss. This only
 *    does anything for elements that can take focus, so callers whose content
 *    is worth reaching pass their own `tabIndex={0}`; on touch, tapping such
 *    an element focuses it and the card appears.
 *  - **assistive tech** — the same text as an `aria-label`, so it is in the
 *    accessible tree whether or not the element is ever focused or hovered.
 *
 * Pair with `<Tooltip tip={tip} />` once per view.
 */
export const useTooltip = () => {
  const [tip, setTip] = useState<TooltipState | null>(null);

  const show = useCallback((e: { clientX: number; clientY: number }, content: TooltipContent) => {
    setTip({ ...content, x: e.clientX, y: e.clientY });
  }, []);
  const hide = useCallback(() => setTip(null), []);

  /** Focus carries no pointer coordinates, so anchor to the element itself. */
  const showAtElement = useCallback((el: Element, content: TooltipContent) => {
    const r = el.getBoundingClientRect();
    setTip({ ...content, x: r.left + r.width / 2, y: r.top });
  }, []);

  // Escape dismisses, matching every other transient overlay. Only listens
  // while something is actually shown.
  useEffect(() => {
    if (!tip) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setTip(null);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [tip]);

  /**
   * Spread onto any element to give it a tooltip.
   *
   * `label: true` also emits an `aria-label`. It is opt-in, not automatic: an
   * unconditional label overrides the accessible name of whatever it lands on,
   * which is right for a bare shape (a chart bar, a map dot, a grid cell) that
   * has no text of its own, and wrong for a container whose visible text
   * already says the same thing. Ask for it only where the element would
   * otherwise be nameless.
   */
  const bind = useCallback(
    (content: TooltipContent, opts?: { label?: boolean }) => ({
      onMouseEnter: (e: React.MouseEvent) => show(e, content),
      onMouseMove: (e: React.MouseEvent) => show(e, content),
      onMouseLeave: hide,
      onFocus: (e: React.FocusEvent) => showAtElement(e.currentTarget, content),
      onBlur: hide,
      ...(opts?.label ? { 'aria-label': describe(content) } : {}),
    }),
    [show, hide, showAtElement]
  );

  return { tip, show, hide, bind };
};
