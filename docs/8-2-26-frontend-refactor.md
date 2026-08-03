# Frontend Review — 2026-08-02

> **Status: implemented, review fixes in progress, no PR yet.**
> Everything below was fixed on branch `frontend-refactor-8-2-26`, taking the
> recommended variant in each mockup (A1 · B1 · C1 · D1 · E1 · F1 · G1). See
> [What shipped](#what-shipped) for the mapping from finding → change.
>
> A second-pass code review then found further defects — all fixed. See
> [Review pass](#review-pass--where-we-left-off) at the bottom for what it
> found, including one real bug (weekday grouping computed off UTC, putting
> Friday night football on Saturday) and two things still owed.

Full pass over every view in the running app (Vite dev server + live SQLite, 235 attended
games, 7 leagues), in **both themes**, driven through Chrome. Findings are grouped by
impact, and each one says what was actually observed rather than what the code implies.

Status legend: **[bug]** = something is visibly broken or unreadable · **[gap]** = works,
but wastes the space or the data it has · **[idea]** = additive.

Where a fix has more than one reasonable shape, there is a mockup — see
[Mockups](#mockups) at the bottom. Those are the decisions I need from you.

---

## Tier 1 — Broken or unreadable (fix regardless)

### 1.1 `SeasonChart` renders 4× oversized on the Map page **[bug]**

`components/find/SeasonChart.tsx` draws into a fixed `viewBox="0 0 300 110"` and is styled
`className="w-full"`. SVG scales the *whole coordinate system*, text included, so the
component's real size is whatever its container happens to be. Measured live at a 1768px
viewport:

| Where | Container | Rendered | Scale | Effective axis-label size |
|---|---|---|---|---|
| Map view, "Games per season, all leagues" | full-width panel | **1182 × 433 px** | **3.94×** | **37 px** |
| Stats page, right rail | 340px rail | 306 × 112 px | 1.02× | 9.7 px |
| Team workspace, right rail | 320px rail | 286 × 105 px | 0.95× | 9.1 px |

So the two rails are fine at desktop — the component was clearly designed for a ~300px box —
and the Map page is the acute failure: a **433px-tall** chart with 37px axis numbers that
dominates everything below the map.

The fragility is general, though. Both rails are `lg:grid-cols-[1fr_320px]`, so **below the
`lg` breakpoint they stack full-width** and the chart blows up there too. Any future use in
a wide panel has the same problem.

Fix: stop scaling text with the viewBox — set the `<text>` font-size in CSS so it stays in
screen pixels, or measure the container and lay the chart out in real pixels (what mockup
**A1** does). Pin the height while you're there.

→ Mockup **A** offers three shapes for this chart.

### 1.2 The last x-axis label is clipped on every season chart **[bug]**

With a 1992–2025 range and `tickEvery = 5`, the 2025 tick is centred at x≈296 in a 300-wide
viewBox. The label is ~14px wide, so it runs to x≈303 and the viewBox cuts it. Every season
chart in the app currently ends in **`'2`** instead of **`'25`**.

Visible on every season chart in the app — subtle in the rails, and 37px tall on the Map
page where it's impossible to miss.

Fix: reserve right padding in the viewBox (`W - PAD_RIGHT` for the plot area), or anchor
the final tick `end` instead of `middle`.

### 1.3 The Profile page is unreadable in dark mode **[bug]**

`pages/Profile.tsx` uses hard-coded legacy Tailwind colours (`text-gray-900`,
`text-gray-600`, `bg-white`) that don't participate in the token system. In dark mode the
`My Profile` heading and the `Manage your account settings` subtitle render as near-black
text on the near-black page background — they are, in practice, invisible. The two cards
stay hard-coded white, so the page is a white slab on a dark app.

This is specifically a *Profile* problem, not an auth-page problem: Profile renders **inside
`<Layout>`**, so it inherits the themed `--page` background while its own text stays
hard-coded dark. Login and Register paint their own full-page light gradient and are
self-consistent — jarring next to the rest of the app, but readable. (Their input
placeholders are very washed out, though — see §4.7.)

### 1.4 The loading state is legacy-coloured and drops the app shell **[bug]**

`components/common/Loading.tsx` is `text-gray-700` on `min-h-screen` with no `bg-page`, and
it is the **full-page** return value for Statistics, MyGames, TeamDetail and MapView:

```tsx
if (loading) return <Loading message="Loading statistics..." />;
```

Two problems. First, `text-gray-700` (#364153) on the dark `--page` (#131417) is roughly a
2:1 contrast ratio — below any accessibility floor. Second, because `Loading` is returned
*instead of* `<Layout>`, the header and nav unmount on every page load and remount when data
arrives — a visible shell flash on each navigation.

Fix: render the spinner *inside* `<Layout>` (or better, skeleton the panels), and move it
onto the tokens.

### 1.5 Dark team logos disappear on dark panels **[bug]**

Logos are PNGs on transparent backgrounds. Teams whose primary mark is black or navy
vanish against `--panel` (#1b1e24) in dark mode. Confirmed by inspection — the images load
fine (`naturalWidth: 500`) and render at 24×24, they're just invisible:

- San Antonio Spurs (`/logos/nba/63.png`) — black/silver
- Anaheim Ducks (`/logos/nhl/45.png`) — black/gold
- New York Yankees, Michigan State, New Orleans Saints, Atlanta Falcons — same story

This hits the My log ledger, the Find "Your teams" chips, the omnibox dropdown, and the
team workspace game log. Roughly a quarter of the pro-league rows.

Fix options: a subtle light plate behind every badge in dark mode, or a per-logo luminance
check at scrape time, or a CSS drop-shadow ring. → Mockup **B**.

### 1.6 The wordmark says "six leagues"; there are seven **[bug]**

`components/layout/Header.tsx` line 42: `Games attended · six leagues`. MLS shipped and the
Stats page happily shows seven league chips. One-word fix, but it's on every page.

---

## Tier 2 — Structural: the layout wastes the space it has

### 2.1 The team workspace right rail strands ~40% of the page **[gap]**

The workspace is `grid lg:grid-cols-[1fr_320px]`. The game log runs 100 rows (~3,500px);
the stats rail is ~500px tall and then stops. Scrolling Alabama's log means staring at a
320px-wide empty column for the remaining 3,000px, while the stat tiles, the season chart
and the venue bars — the things you'd actually want to correlate against the rows you're
reading — have scrolled off the top.

Fix: `position: sticky` on the rail, or move the summary into a horizontal band above the
log. → Mockup **C**.

### 2.2 The game log table has no sticky header **[gap]**

Same page: `Date / Matchup / Result / Venue / Passport` scroll away after ~20 rows. By row
60 you're reading an unlabelled five-column table. `position: sticky` on `<thead>`.

### 2.3 The Find home page leaves 45% of the height and 57% of the width empty **[gap]**

Measured at a 1768×942 viewport: content ends at y=518, so **45% of the height is empty**,
and the inner column is capped at `max-w-3xl` (768px) inside a `max-w-7xl` (1280px) main —
**57% of the width unused**. This is the app's front door and it currently shows a heading,
a search box, and eight chips.

The data to fill it already exists in `GET /api/attendance/stats` and
`/api/attendance/venues`, both of which the page could call. → Mockup **D** proposes three
things to put there.

### 2.4 The My log ledger has a dead gutter and no way to filter 235 rows **[gap]**

Two issues in one row layout:

- **Dead space**: the venue text ends around 60% of the row width and the
  `Add notes` / `Remove` buttons are pinned right with `ml-auto`, leaving ~270px of nothing
  in the middle of every row on a wide screen.
- **No filtering**: 235 rows, rendered all at once, in one flat reverse-chronological list.
  No league filter, no season filter, no venue filter, no search, no sort. The Find page has
  league chips; the Map page has league chips; the log — the one view with hundreds of rows —
  has none.

→ Mockup **E**.

### 2.5 The venue panel on the Map double-scrolls inside empty space **[gap]**

`MapView.tsx` caps the games list at `max-h-72` with `overflow-y-auto`, inside an `aside`
that is already stretched to the map's height by `items-stretch`. Result: for Bryant-Denny
(76 games) you get a **5-row scroll window** with ~65px of unused panel below it, and a
nested scrollbar. Let the list fill the aside.

### 2.6 The omnibox league chips wrap to a second row in the team workspace **[gap]**

`TeamDetail.tsx` wraps the switcher in `max-w-xl` (576px). Eight chips
(All leagues + 7 leagues) don't fit, so **MLS drops to its own line**, pushing the team
identity down. Either widen the switcher, drop the chips from the compact variant, or make
the chips a single scrollable strip.

### 2.7 Attended vs unattended rows are distinguished only by `opacity-75` **[gap]**

In a typical team log, 90%+ of rows are unattended, so the dominant visual state is
"dimmed", and the page reads as washed-out. Meanwhile the `ATTENDED` stamp lives in the
last column, ~350px away from the matchup it refers to. Consider inverting: full ink for
everything, and *positively* mark the attended rows (tinted row background + stamp near the
matchup).

### 2.8 The "Teams seen most" bars are unreadable past rank 1 **[gap]**

Alabama is 149 games; ranks 2–8 are 29, 17, 14, 13, 12, 11, 10. Scaled linearly against
149, every bar below Auburn sits between 7% and 12% of full width — visually
indistinguishable, so the chart carries no information below rank 2. It also drops the team
logos that appear everywhere else in the app.

→ Mockup **F**.

---

## Tier 3 — Real estate that could carry more information

### 3.1 The omnibox dropdown wastes ~400px per row **[idea]**

Each result is `[badge] Name Nickname ......... N attended`. Between the nickname and the
count there is ~400px of nothing. Candidates for that space: conference, active season
range, your record against/with them, venues seen.

It also has a **relevance problem**: searching "michigan" returns *Michigan A.C.* and
*Michigan Military Academy* (defunct 1890s programs) above *Michigan State* and *Michigan
Tech*, with nothing marking them as historical. Showing `1896–1901` on inactive teams would
fix the confusion for free, and it's already in `first_season`/`last_season`.

### 3.2 Stats page: no record, no streaks, no venue leaderboard **[idea]**

The passport page has four hero tiles (games / venues / states / years) and then league
chips, a tile map, top teams, and games-per-season. Things it knows but doesn't show:

- **Overall record when attended** — the team workspace computes W–L–T per team; the
  aggregate is the single most "passport" stat in the app and it's absent
- **Most-visited venues** — `/api/attendance/stats` returns `venues` already; unused here
- **Longest gap / longest streak**, busiest month, favourite day of week
- **Home vs away split**, average total points, biggest blowout, closest game
- **New venues per year** (the "collector" metric)

### 3.3 The Map has an unused choropleth layer **[idea]**

The state boundaries are drawn (`STATE_BORDERS_PATH`) but every state is filled the same
`var(--panel)`. The Stats page already computes `games_by_state` and shades a tile grid with
it. Shading the real map with the same scale would make the two views consistent and give
the Map something to say at a glance. → Mockup **G**.

### 3.4 Hover states carry almost nothing **[idea]**

Inventory of what exists today:

| Element | Hover shows |
|---|---|
| Map dot | `Name · N games` (and only on mouse *movement* — `onMouseMove`, not `onMouseEnter`, so a stationary pointer shows nothing) |
| Tile map state | native `title`: `AL: 96 games` |
| Season chart bar | native `<title>`: `2025: 12 games` |
| Team bar (Stats) | native `title`: full team name |
| Ledger row | nothing |
| Game log row | nothing |
| Stat tiles | nothing |

Native `title` tooltips have a ~1s delay, can't be styled, and don't work on touch. The Map
already has a custom tooltip component — worth promoting it to a shared one and using it
everywhere. Candidates: venue tooltip → league mix + first/last visit + your record there;
season bar → the actual games that year; stat tile → how it's computed.

### 3.5 The venue panel could be a venue *page* **[idea]**

Clicking a dot gives name, city, count, and a game list. It could also give: first and last
visit, your record there, which teams you've seen there, home/away split, and a link to
"all games at this venue".

### 3.6 Selecting a venue doesn't mark it on the map **[idea]**

`selected` drives the aside but nothing on the SVG. A selected dot should get a ring, and
ideally the others should dim.

### 3.7 The stamp shelf shows exactly six, always **[idea]**

`attendedGames.slice(0, 6)` in a `flex` container with `overflow-x-auto`. On a wide monitor
that leaves ~40% of the shelf empty; on a phone it's a 6-wide horizontal scroll. Make the
count responsive, or make the shelf a genuine horizontal scroller through the whole log.

---

## Tier 4 — Consistency and polish

### 4.1 Two design systems are live at once

The Press Box token system covers Find / Map / My log / Stats / Team. Everything else is on
the pre-redesign green-and-white palette. 105 hard-coded legacy colour classes remain:

| File | Occurrences |
|---|---|
| `pages/Admin.tsx` | 48 |
| `pages/ResetPassword.tsx` | 13 |
| `pages/ForgotPassword.tsx` | 9 |
| `pages/Profile.tsx` | 9 |
| `pages/Login.tsx` | 8 |
| `pages/Register.tsx` | 7 |
| `components/common/Button.tsx` | 3 |
| `components/common/Alert.tsx` | 2 |
| `components/common/Input.tsx` | 2 |
| `components/common/Loading.tsx` | 1 |

The four `components/common/*` entries matter most — `Alert` and `Loading` are rendered *by
the redesigned pages*, so the legacy palette leaks into the new design on every error and
every page load. Those four are a small, high-value fix. Admin is a bigger job and can wait.

`index.css` still carries the whole legacy `@theme` block (primary-*/accent-*/sage-*) plus
`.card-elevated`, `.gradient-*`, `.section-spacing` — dead once the pages above move.

### 4.2 Nav label vs. page heading

Header says **"Find games"**, **"My log"**, **"Stats"**; the pages say "Find games" (kicker),
"My log" (kicker), "Record of travel / Your passport". The Stats mismatch is the odd one —
nothing on the page is called "Stats".

### 4.3 `34 yrs` renders with a mono-font gap

`Statistics.tsx` builds `${lastYear - firstYear + 1} yrs`; the mono font gives it a wide gap
next to the three bare numerals in the other tiles. Cosmetic; consider `34` with `years` in
the kicker instead.

### 4.4 The tile map strands AK and HI

`TileMap.tsx` places AK at (1,1) and HI at (1,7) — two isolated tiles with a full empty
column between them and the mainland, in a dataset with no non-continental games. The Map
view already made the call to drop Alaska and Hawaii from the projection
(`SP3_frontend_redesign.md` Phase 4). The tile map should match.

### 4.5 Dark-mode legend swatches for 0 and 1–2 are indistinguishable

`inkFor(0)` is `var(--panel-2)`; `inkFor(1)` is `color-mix(... --focus 20%, --panel-2)`. In
dark mode those two swatches are nearly identical in the legend.

### 4.6 Auth-page placeholders are near-invisible

On Login and Register the placeholder text (`John Doe`, `you@example.com`) sits at roughly
the same lightness as the input's own background — legible only if you're looking for it.
Comes from `components/common/Input.tsx` inheriting the browser default placeholder colour
against a very light field. Worth fixing when those pages move to tokens (§4.1).

### 4.7 Mobile is still unverified

`SP3_frontend_redesign.md` Phase 6 flags this as open and it still is. Reading the
breakpoints: the tables fall back to horizontal scroll (`min-w-[560px]` on the game log,
`w-max` on the tile map) and the nav collapses correctly, so nothing should be *broken* —
but the map, the omnibox and the stamp shelf deserve a real device pass. I could not
resize the browser viewport in this session (the window is maximised and
`resize_window` didn't take), so **this section is from code, not observation** — treat it
as unverified.

---

## Mockups

**`docs/mockups/8-2-26-frontend-refactor-mockups.html`** — one self-contained page, no
dependencies, no network access needed (team logos are inlined as data URIs). It uses the
app's real CSS tokens and your real 235-game log, and has its own light/dark toggle, so what
you see is what it would look like shipped.

To view it, open the file directly in a browser, or:

```bash
cd docs/mockups && python -m http.server 8899
# then http://127.0.0.1:8899/8-2-26-frontend-refactor-mockups.html
```

| # | Section | Variants | My pick |
|---|---|---|---|
| A | Season chart | A1 fixed-height responsive · A2 sparkline + hover · A3 heatmap strip | **A1** (A2's richer tooltip needs a per-season league/record breakdown from the API) |
| B | Dark logos | B1 plate on all · B2 contrast ring · B3 per-logo plate from a scrape-time flag | **B1** now, B3 later |
| C | Team workspace | C1 sticky rail · C2 summary band + full-width log | **C1** |
| D | Find home page | D1 "on this date" + stamps · D2 passport dashboard · D3 upcoming games | **D1** (D3 is the best idea but needs an endpoint) |
| E | My log | E1 filter bar + filled gutter · E2 grouped by season, hover actions | **E1** + steal E2's hover-reveal |
| F | Teams seen most | F1 vs-runner-up (hatched leader) · F2 √-scale | **F1** |
| G | Map | G1 choropleth + dots | **G1** |

Each section also shows the *current* state (B0, F0, G0) next to the alternatives so the
comparison is direct.

---

## Suggested order of work

1. **Tier 1 in one pass** (1.1–1.6). Mostly small, all user-visible, and 1.1/1.2 are one
   file. Half a day.
2. **`components/common/{Loading,Alert,Button,Input}.tsx` onto tokens** (§4.1). Four small
   files, and it stops the legacy palette leaking into the redesigned pages.
3. **Whichever of C / D / E you pick.** These are the real design decisions; each is
   self-contained.
4. **Tier 3 additions**, driven by whatever you actually want to see on the Stats page.
5. **Admin + auth pages onto tokens**, then delete the legacy `@theme` block from
   `index.css`. Biggest chunk, least urgent — Admin is a single-user page you rarely open.

---

## Method / caveats

- Reviewed against the live Vite dev server and the real SQLite database (235 attended
  games, 63 venues, 7 leagues), driven through Chrome, in both themes.
- Measurements (chart widths, contrast, empty space) were taken from the live DOM, not
  estimated from source.
- **Not verified:** narrow/mobile viewports. The browser window was maximised and could not
  be resized in this session, so §4.6 is a code reading only.
- Written as a review; the implementation followed on the same branch (below).

---

## What shipped

Branch `frontend-refactor-8-2-26`. Recommended variant taken in every mockup.

### Tier 1

| # | Change |
|---|---|
| 1.1 | `SeasonChart` rewritten: viewBox tracks the measured container (`ResizeObserver`), so 1 unit = 1 CSS px and axis text is a fixed 10px at any width. Height pinned (default 132px). |
| 1.2 | Final tick anchors `end` and clamps inside the plot — `'25` no longer clipped. |
| 1.3 | `Profile.tsx` on tokens. |
| 1.4 | `Loading` renders **inside** `<Layout>` so the nav no longer unmounts on every page load; a bare `Spinner` export covers `ProtectedRoute`, which must not flash the signed-in chrome. |
| 1.5 | `.logo-plate` — light backing behind every logo in dark mode (mockup **B1**). |
| 1.6 | "six leagues" → "seven leagues". |

### Tier 2

| # | Change |
|---|---|
| 2.1 | Stats rail `lg:sticky lg:top-20` (mockup **C1**). |
| 2.2 | `.sticky-head` on the game log `thead`, offset to clear the page header. The panel's `overflow-x-auto` became `max-lg:overflow-x-auto` — `overflow-x` forces the other axis to `auto`, which would have made the panel the scroll container and killed the sticky. |
| 2.3 | Find home page: "on this date" + latest stamps + your teams (mockup **D1**), column widened to `max-w-5xl`. |
| 2.4 | My log: search + league chips + season select + live "N of 235" + Clear; gutter now carries city/state and a home-result chip; `Remove` revealed on hover/focus (mockup **E1** + E2's hover-reveal). |
| 2.5 | Venue panel list fills the aside instead of a 5-row `max-h-72` window inside empty space. |
| 2.6 | Team-page omnibox `max-w-xl` → `max-w-3xl`; the MLS chip no longer wraps. |
| 2.7 | Emphasis inverted — attended rows get a `--stamp` tint, unattended rows keep full ink. |
| 2.8 | Top teams scale to the runner-up with a hatched, off-scale leader (mockup **F1**). |

### Tier 3

| # | Change |
|---|---|
| 3.1 | Omnibox rows show conference/city, and an era (`1896–1901`) on teams whose last season is past — the fix for "Michigan A.C." outranking Michigan State with nothing marking it as defunct. |
| 3.2 | Stats page gained a second tile row (home-team record, busiest day, busiest month, longest gap) and a most-visited-venues panel. Backed by new `/api/attendance/stats` fields. |
| 3.3 | Map choropleth (mockup **G1**) — `STATE_PATHS` added to `usOutline.ts`, keyed by 2-letter code so it indexes straight into `games_by_state`. |
| 3.4 | Shared `useTooltip()` + portalled `<Tooltip>` replaces native `title=` on stat tiles, league chips, top teams, venues, tile-map states, chart bars and map dots. Binds `mouseenter` **and** `mousemove` — the old map tooltip bound move only, so a stationary pointer showed nothing. |
| 3.5 | Venue panel gained the home record there, the visit era, and a top-teams-seen line; team names link through. |
| 3.6 | Selected dot gets a ring and the others dim. |
| 3.7 | Stamp shelf is a real horizontal scroller (12 stamps) rather than a hard six. |

### Tier 4

All legacy colour classes are gone — `Admin`, `Profile`, `Login`, `Register`,
`ForgotPassword`, `ResetPassword`, `Card`, `Button`, `Input`, `Alert`, `Loading` are on
tokens, and the `primary-*`/`accent-*`/`sage-*` `@theme` block plus `.card-elevated`,
`.gradient-*` and `.section-spacing` are deleted from `index.css`. Nav label `Stats` →
`Passport` to match the page heading; the tile map dropped AK/HI (matching the Atlas
projection) and its "0" legend swatch is now an outline, not a near-identical tint.

### Went beyond the review

Three things the review didn't call for but the work exposed:

1. **`games_by_team` merged teams that share a name.** It is keyed by name, so Alabama's
   CFB and CBB sides were one bucket — the Stats page read 149 where CFB alone is 147. The
   new `top_teams` field keys on team id and carries league, logo and abbreviation, which
   is also what made F1's logos possible. `games_by_team` is unchanged for compatibility.
2. **A failed sync had no visible cause.** The Admin table put the error text in a
   `title=` only; it now prints under the table.
3. **`overflow-x: auto` forces the other axis to `auto`.** This silently broke the sticky
   table header and gave the rotated stamp cards a stray vertical scrollbar and clipped
   corners. Fixed in three places; called out in comments so it doesn't come back.

### Backend

`GET /api/attendance/stats` gained `home_wins/losses/ties`, `top_teams`,
`games_by_weekday`, `games_by_month`, `season_breakdown`, `new_venues_by_season`, and
`longest_gap_days/start/end`. All defaulted, so nothing about the response is breaking.
Notable detail: unplayed fixtures (both scores null) are excluded from the record rather
than counted as ties, and the gap is measured in **calendar** days — raw `timedelta.days`
floors an 83-hour gap to 3 days when a reader means 4. Seven new tests in
`tests/test_attendance.py` pin all of it.

### Verification

All four required checks clean, plus a browser pass over every view in both themes:

```
backend:  ruff ✓   pyright 0 errors ✓   pytest 345 passed ✓
frontend: eslint ✓   tsc ✓   vite build ✓
```

### Still open

- **Mobile (§4.7) remains unverified.** The browser window would not resize in this
  session, so narrow-viewport behaviour is still code-reading only. The changes here
  should help (`lg:` guards on the sticky rail, `max-lg:` on the log's horizontal scroll,
  a wrapping filter bar), but it wants a real device pass.
- `stats.games_by_team` is now unused by the frontend. Kept deliberately; delete it when
  you're sure nothing external reads the endpoint.

---

## Review pass & where we left off

A fresh reviewer went over `git diff main...HEAD` cold. It confirmed the four checks pass
and that the token migration is genuinely complete (zero fixed-palette Tailwind colours
left anywhere under `frontend/src`), then found the following. **Everything marked ✅ is
fixed and committed; the ⏳ items are the ones to pick up.**

### Fixed

| ✅ | Finding | Fix |
|---|---|---|
| **B1** | **`games_by_weekday`/`games_by_month` were computed off the stored UTC instant.** `games.start_date` is always UTC, so any US evening kickoff rolls into the next UTC day. On the real 235-game log, **90 rows start before 07:00 UTC**: the endpoint returned Sat 142 / Fri 18, where the local dates the app actually prints give Sat 115 / Fri 54. Friday night football was being counted as Saturday, and the new "Busiest day" tile is a headline number. | New `utc_to_eastern()` in `services/adapters/local_time.py`, used for weekday, month and the gap measurement. Eastern for the same reason the rest of that module uses it — no venue timezone is stored, every venue is North American, and it is the wall clock the bulk sources publish in. `has_time=False` rows are unaffected (parked at noon UTC by `DATE_ONLY_HOUR`). |
| **F1** | **Duplicate React keys** in "Most-visited venues": keyed on `name`+`city`, but the backend deliberately counts same-named venues separately by id. This DB has three colliding pairs (three separate Madison Square Garden rows, two MetLife, two Caesars Superdome) — latent only because just one of each currently reaches the top 8. | `venue_id` added to `AttendanceVenueCount`; both Statistics and TeamDetail key on it. |
| **F5** | Attended rows on the team log **lost their hover feedback** — the inline `background-color` outranked `hover:bg-panel-2`. | Moved to an `.attended-row` class with its own `:hover` step. Note an unlayered class alone would *not* have fixed it: unlayered CSS outranks `@layer utilities` regardless of specificity, so the hover state is declared explicitly. |
| **F3** | My log's hover-revealed row actions were `opacity-0` but **still hit-testable** — an invisible clickable target over every row. | `pointer-events-none` gated with the same hover/focus-within conditions. |
| **F4** | "Clear filters" was inferred from `visible.length !== total`, so a filter matching every row (one-league user clicking their only chip) showed no Clear button. | Derived from the control state instead. |
| **F6** | SeasonChart's last tick was anchored `end` unconditionally, so when it *didn't* overflow it sat half a label left of the gridline every other tick uses. | Anchor now follows the same overflow test as the clamp. |
| **F7** | Version-skew guarding was inconsistent — `top_teams` was guarded but `games_by_weekday`, `games_by_month`, `season_breakdown` and `new_venues_by_season` would throw and blank the page on exactly the skew the comment described. | All new fields read through `?? {}` / `?? []`. |
| **R1** | TileMap dropped the AK/HI tiles but still summed them into the percentage denominator, so a Hawaii game would silently vanish while skewing every other tile. DC has the same shape (the new choropleth *will* shade it; the tile grid has no tile for it). | An "Off the grid: HI 2 · DC 1" line appears when any state has games but no tile. |
| **R3** | `.logo-plate`'s ring was `var(--line)` — a 9%-white hairline on an always-light plate, i.e. invisible in the only mode the rule applies in. | Dark ring instead. |
| **F9** | `truncate` on an inline `<span>` in the omnibox was inert (`overflow` doesn't apply to non-replaced inline boxes). | Moved to the block wrapper. |
| **F10** | Find printed the year with raw `getFullYear()` and MapView hard-coded `has_time=false`, both bypassing the timezone-aware `yearOf`. | Both use `yearOf` with the row's real `has_time`. |

### Also fixed (second sitting)

| ✅ | Finding | Fix |
|---|---|---|
| **B1 tests** | Nothing pinned the timezone fix — `test_weekday_month_and_longest_gap` passes either way, because its fixture sits at 23:30 UTC on a Saturday, which is Saturday in Eastern too. | Three cases added, and **verified to fail without the fix**: reverting the conversion makes the night-kickoff case report Tuesday instead of Monday. The 2024 CFP final (played Monday 8 Jan 7:30pm ET, stored `2024-01-09 00:30`) is the fixture. A companion case pins that `has_time=False` rows at noon UTC are *not* rolled off their own day by the conversion, and a third checks `venues[].venue_id` is present and unique. |
| **F2** | The tooltip rewrite was mouse-only — `useTooltip` bound only mouse events, the triggers were non-interactive elements with no `tabIndex`, and nothing exposed the text to assistive tech. Replacing native `title=` had made the information *less* reachable than what it replaced. | `bind()` now covers three paths and says so in its docstring: mouse (enter + move), keyboard/touch (focus/blur, anchored to the element's own rect since focus carries no coordinates, plus Escape to dismiss), and assistive tech (the same text as an `aria-label`, so it is in the accessible tree without needing hover or focus at all). Trigger elements gained roles that make the label legitimate — `role="group"` on the stat tiles, chips and venue rows, `role="img"` on tile-map cells, `role="graphics-symbol"` on chart bars and state fills; `aria-label` on a role-less `<div>` is unreliable and can mask the element's own text. |
| **F2 follow-on** | The map's venue dots were **not keyboard-operable at all** — selecting a venue was mouse-only, which the review surfaced while looking at tooltips. | Dots are now `role="button" tabIndex={0}` with Enter/Space handling and a visible focus ring. They are the map's primary control, so unlike the ~30 chart bars per chart they earn a tab stop; the bars deliberately stay out of the tab order and rely on their accessible names. |

### ⏳ Outstanding

1. **Mobile is still unverified** (§4.7) — unchanged. The reviewer also noted **R2**:
   `.sticky-head` is inert below `lg`, because `max-lg:overflow-x-auto` makes the panel a
   scroll container on both axes (the exact trap documented in CLAUDE.md) and its auto
   height means it never scrolls vertically. Deliberate scoping — the sticky header is an
   `lg+` feature — but worth knowing.

2. **The a11y changes were not re-verified in a browser.** The Chrome extension
   disconnected before the last pass, and installing Playwright purely for this check
   wasn't worth polluting the project. They are attribute- and handler-level changes and
   tsc/eslint/build/tests are all green, but a real screen-reader and keyboard pass on the
   Passport and Map pages is still owed.

### Checked and explicitly found fine

Worth not re-litigating: the no-attendances early return does satisfy the response model
(Pydantic v2 deep-copies mutable defaults per instance); a single game leaves all three
`longest_gap_*` as `None`; null scores are correctly excluded from the record rather than
counted as ties; `venue_first_season` is order-independent; there are **no conditional
hook-order violations** anywhere; SeasonChart's `ResizeObserver` is disconnected on
cleanup and cannot `setWidth` after unmount; `Tooltip` cannot render-loop; the `@theme`
deletion orphaned nothing; and `STATE_PATHS` correctly drops the five territories that
`geoAlbersUsa` refuses to project.

The reviewer also verified the aggregation against the **real** 235-game database:
`sum(season_breakdown.games) == sum(games_by_weekday) == total_games == 235` and
`sum(new_venues_by_season) == unique_stadiums == 63`.

### State of the branch

`frontend-refactor-8-2-26`, three commits, all four checks green
(ruff · pyright · **348** pytest · eslint · tsc · build).

One repo hazard worth remembering: `npm run build` empties `backend/static/` and deletes
the tracked `backend/static/.gitkeep`. Restore it (`git checkout backend/static/.gitkeep`)
before committing after a build.
