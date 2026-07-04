# Social Pressure — UI Direction Mockups

Three genuinely distinct pitch directions for the accountability-partner PWA. Each is a
single self-contained HTML file showing all five core screens (plus a "logged" confirmation
state) as 390px phone frames in a horizontally scrollable row.

All three are built to the real constraints: mobile-first at 390px, implementable as
server-rendered Django templates + a hand-written CSS file + tiny vanilla JS, no framework,
no build step, inline SVG / emoji only, at most one Google Font per direction. Content is
realistic throughout: **Gym Buddies** — Henry (target 3/week, on 2) vs Daniel (target 2/week,
on 2, 4-week streak), with a live history feed, emoji reactions, and a nudge.

Open any file directly in a browser.

---

## Direction 1 — **Ledger**
**Personality:** A stark accountability register. The accountant's view of your discipline —
ink on paper, everything reconciles against a target.

- **Palette:** paper `#f4f2ec`, card `#fbfaf6`, ink `#1a1a17`, faded ink `#5a574d`,
  hairline rule `#d8d4c7`, signal red `#c0392b`, deep green `#0f4c3a` (used once, for the
  "posted" confirmation only).
- **Type:** IBM Plex Mono across the board — data, labels, and body. Monospace makes every
  numeral line up; the whole UI reads as a ledger.
- **Structurally different:**
  - Progress-vs-partner is a literal **ledger**: right-aligned tabular fractions (`2 / 3`),
    hairline paired bars with a target tick, and `−1` / `met` flags. No avatars beyond a
    22px monogram box.
  - Hairline rules and hard corners everywhere (zero border-radius on content); density is
    high and disciplined. Sections are separated by 1px rules, not cards or shadows.
  - "Behind" is encoded as a diagonal-hatched red fill — it looks like a flagged line item,
    not a mood.
  - Microcopy is terse and financial: "Open accounts," "reconciled against target,"
    "Entry posted," "1 to go — 2 days left."

## Direction 2 — **Roster**
**Personality:** Warm, human, rounded. The gym buddy who texts you, not the spreadsheet
that shames you. Partners are people first.

- **Palette:** warm cream `#f7f1e7`, card `#ffffff`, terracotta/you `#d9603b`,
  partner sage `#5c7a56`, streak gold `#e0a838`, soft brown ink `#38332c`, line `#eae1d2`.
  Each member owns a color (you = clay, partners = sage/plum/blue).
- **Type:** Fraunces (warm optical serif) for display/headings + Inter for body and data.
  Serif carries the friendliness; Inter keeps numbers legible.
- **Structurally different:**
  - Progress is shown as **goal-dots** — filled beads on a string (2 filled + 1 dashed
    "still open"), plus a big Fraunces fraction. Reads as a warm gauge, not a bar chart.
  - Everything is a rounded card with generous whitespace and soft shadows; the layout
    breathes rather than packs.
  - Real 46px circular avatars lead every row; notes render as chat-style speech bubbles;
    the feed reads like friends cheering ("Daniel went to the gym," "leg day — squat PR 🎉").
  - Copy is second-person and encouraging: "Morning, Henry," "Three people are counting on
    you," "Did you make it?", "Nice. That's logged."

## Direction 3 — **Arena**
**Personality:** A scoreboard for your discipline. Dark stadium energy, condensed uppercase
type, every partnership rendered as a head-to-head race. For people who show up when someone's
watching the tape.

- **Palette:** stadium night `#0b0e14`, panel `#141922`, electric lime/you `#c8f94a`,
  magenta/rival `#ff3d78`, streak amber `#ffb020`, cyan `#38d6e0` (tie state), text `#eef2f7`.
- **Type:** Archivo + Archivo Expanded (heavy condensed, uppercase, occasional italic) — a
  sports-broadcast display voice. Big score numerals dominate.
- **Structurally different:**
  - Progress-vs-partner is a literal **race down two lanes**: your lime lane vs the rival's
    magenta lane, a `VS` divider between them, goalposts at target, and giant condensed
    score numerals (`2/3`). The home screen is "Standings"; each project is a "matchup."
  - Dark, high-contrast, high-energy — the inverse of the other two. Color does the work:
    lime is always you, magenta is always them, amber is streak fire.
  - A running **clock** ("2 DAYS LEFT") sits under every project header; the log screen shows
    a `Now 2/3 → After 3/3` score preview to frame the tap as scoring a point.
  - Copy is competitive and kinetic: "Put one on the board," "You're down 1," "catch up,"
    "3 of 3. You're level.", "accept the challenge."

---

### Screens covered in each file
1. **Home / project list** — every project at-a-glance with per-member count-vs-target status.
2. **Project screen (the product)** — each member's count vs their own target this period,
   streak, history feed with emoji reactions, and a nudge affordance. Carries the design.
3. **Log event** — one giant tap target, optional note, plus a **3b logged/confirmed** state
   showing instant feedback + "pushed to partner."
4. **Create project** — template pre-fills (Gym buddy / Study partner / Custom), one activity
   (name / unit / cadence), end date or indefinite, with a plain-language recap line.
5. **Invite-accept** — arriving via link: see the project + partner, set your own per-member
   target with a stepper, join.
