## Design tokens and layout gotchas

Light/dark via CSS-var tokens.
**Every page is on the token system** — there is no legacy `primary-*`/`accent-*`/`sage-*`
palette any more, so a new page should reach for `bg-panel` / `text-ink` / `border-line`,
never a fixed Tailwind colour that can't follow the theme.

Traps worth knowing before touching layout:
`overflow-x: auto` computes the **other** axis to `auto` as well — that silently turns a
panel into a scroll container, which breaks any `position: sticky` inside it and adds
stray vertical scrollbars; scope it (`max-lg:overflow-x-auto`) or pair it with an explicit
`overflow-y-hidden`. Its companion: a grid/flex **item** won't shrink below its content
unless it is *itself* the scroll container, so when the scroller is a descendant (the tile
map inside its panel, the stamp shelf inside its) the item stays content-width and pushes
the whole page sideways on narrow screens — give those items `min-w-0`. And an SVG with a fixed `viewBox` plus `w-full` scales its **text**
with the box, so a chart sized for a 300px rail renders 37px labels in a full-width panel —
size the viewBox from the measured container instead (`components/find/SeasonChart.tsx`).

`npm run build` empties `backend/static/` and deletes the tracked `.gitkeep` in it —
restore it (`git checkout backend/static/.gitkeep`) before committing after a build.

Programmatic `el.focus()` on an SVG shape fires no `focus` event in Chrome, so a keyboard-
accessibility test that calls `.focus()` directly will look broken even when real `Tab`
focus works fine. Test SVG focus behavior with real key events, not `.focus()`.
