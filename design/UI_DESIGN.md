# Social Pressure — UI Design Spec ("Roster")

**Status:** Chosen direction, source of truth for implementation.
This document fully specifies the visual system and all five core screens. It is written
for an implementer who has NOT seen the mockups — everything needed is in here. Where a
value is given, use it exactly; where judgment is needed, the stated principles decide.

Hard constraints (from the project plan, restated):

- Mobile-first, designed at **390px** viewport width. Lives as an installed PWA on phones.
- Server-rendered Django templates + **one hand-written CSS file** + small vanilla JS.
- No React, no CSS frameworks, no build step, no icon fonts. Inline SVG or emoji only.
- Interaction model is server round-trips: full-page loads or small fetch-and-swap.
- Exactly **one** Google Fonts link (specified below).

---

## 1. Personality

**Roster** is warm, human, and rounded: partners are people first, and the UI reads like a
friend cheering you on, not a dashboard grading you. Progress is shown as tactile
"goal-dots" (beads filling on a string) next to real avatars, wrapped in soft white cards
on warm cream, with a friendly serif voice for headings. It is **not** a data tool
(no dense tables, no hard corners, no hairline grids), **not** competitive (no VS framing,
no leaderboards, no red alarms — "behind" is a gentle warm nudge, never shame), and
**not** gamified beyond the streak. Every screen should feel like it was set by a person,
with generous whitespace and one clear action.

---

## 2. Palette

Define these as CSS custom properties on `:root`. No other colors should appear except
derived rgba() shadows/tints of these.

```css
:root {
  /* Backgrounds */
  --cream:      #f7f1e7;  /* page background, everywhere */
  --cream-2:    #fdfaf4;  /* subtle inset surfaces: chips, note bubbles, reaction pills */
  --card:       #ffffff;  /* card surfaces */

  /* Text */
  --ink:        #38332c;  /* primary text — a soft brown-black, never pure #000 */
  --ink-2:      #8a8072;  /* secondary/meta text, placeholders use #b6ab99 */

  /* Lines */
  --line:       #eae1d2;  /* all borders and dividers — warm, low-contrast */

  /* Accent + member colors */
  --clay:       #d9603b;  /* THE accent. The current user ("you") + primary actions */
  --clay-soft:  #f3d9cd;  /* clay tint: "you" highlights, behind-state pills, selected states */
  --sage:       #5c7a56;  /* first partner color; also the success/done color */
  --sage-soft:  #d9e4d4;  /* sage tint: success pills, done confirmation background */
  --gold:       #e0a838;  /* streak warmth + nudge bell; tint background #f9edd4, text on tint #9a7415 */

  /* Extra member colors (3+ member projects), assigned in join order after clay/sage */
  --plum:       #7b5ea7;
  --blue:       #4b7ca8;
}
```

**Usage rules:**

- Page background is always `--cream`. Cards are `--card` with a `1px solid var(--line)`
  border. Nothing sits directly on white except card contents.
- **Clay is always the current user** ("you") and the primary action color. Sage is the
  first partner; additional members get plum, blue, then repeat. Member color assignment
  is per-project, by join order, current user always clay.
- **Success / target met** uses sage (`--sage` text/icon on `--sage-soft` background).
- **Behind state** uses clay, softly: text `#a8451f` on `--clay-soft`. Never a
  saturated red, never an error style. Behind is warm encouragement, not alarm.
- **Streaks and nudges** use gold: `#9a7415` text on `#f9edd4` background.
- Buttons: primary = clay background, white text. Dark neutral button (`--ink` background,
  `--cream` text) is allowed for the home screen's "Start a project" so it doesn't compete
  with in-project clay CTAs.

---

## 3. Typography

One Google Fonts link, in `base.html` `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

Two families, strict division of labor:

- **Fraunces** (serif, optical sizing) — display voice: page titles, card titles,
  member names, big fraction numerals, section headings, the wordmark. Weight 600 almost
  everywhere; italic for occasional emphasis. Fraunces is what makes the app feel warm —
  but use it only for the roles below, never for body text or buttons.
- **Inter** (sans) — everything else: body, meta, labels, buttons, form fields, pills.

Type scale (all sizes px; base body line-height 1.5, headings 1.15–1.25):

| Role | Family | Size | Weight | Notes |
|---|---|---|---|---|
| Greeting / page title | Fraunces | 26–27 | 600 | e.g. "Morning, Henry." — the name in `--clay` |
| Screen heading (create/invite) | Fraunces | 24–25 | 600 | line-height 1.15–1.25 |
| Project title (project screen) | Fraunces | 26 | 600 | |
| Card title (home cards) | Fraunces | 19 | 600 | |
| Member name (member card) | Fraunces | 18 | 600 | |
| Section heading (feed) | Fraunces | 17 | 600 | inline meta suffix in Inter 12/400 `--ink-2` |
| Big fraction numeral | Fraunces | 32 | 600 | "2" in member color; "/3" same size, `--ink-2`, weight 400 |
| Stepper numeral (invite) | Fraunces | 44 | 600 | `--clay` |
| Body / feed line | Inter | 13.5–14 | 400–600 | names bold 600, verbs regular |
| Button label | Inter | 14.5–15 | 600 | |
| Meta / timestamps / captions | Inter | 11–12 | 400–500 | `--ink-2` |
| Pills / badges | Inter | 11–12 | 600 | |
| Form input text | Inter | 15 | 400 | |
| Field labels | Inter | 12 | 600 | `--ink-2` |

Set `-webkit-font-smoothing: antialiased` on body. Wordmark: "Social Pressure." in
Fraunces 600, the trailing period in `--clay`.

---

## 4. Spacing & shape

**Spacing scale** (px): 4, 8, 12, 16, 20, 24, 32. Screen edge padding is **20–22px**.
Cards: 18px internal padding. Vertical gap between stacked cards: 14px. Gap between
distinct page sections: 16–24px.

**Radii** — everything is rounded, generously:

| Element | Radius |
|---|---|
| Cards (project, member, invite detail) | 20–24px |
| Buttons (primary, secondary) | 16–18px |
| Form inputs | 14px |
| Template picker cards | 18px |
| Pills / chips / reaction pills | fully rounded (`border-radius: 999px` or 16–20px on short pills) |
| Avatars, steppers ± buttons, big log button | 50% (circles) |
| Note bubble | `0 14px 14px 14px` (top-left corner square — speech-bubble cue) |

**Shadows** — soft and warm, never gray-blue:

```css
/* resting card */    box-shadow: 0 3px 10px rgba(90,70,50,.05);
/* member card */     box-shadow: 0 4px 14px rgba(90,70,50,.06);
/* clay CTA button */ box-shadow: 0 6px 16px rgba(217,96,59,.35);
/* big log circle */  box-shadow: 0 16px 40px rgba(217,96,59,.4), 0 0 0 10px #fbe4d8; /* halo ring */
```

**Hairlines:** all borders are `1px solid var(--line)` (1.5px on interactive/selected
elements like inputs and the "you" card). No pure-gray `#ddd`-style borders anywhere.

---

## 5. Component patterns

### 5.1 Avatar

Circle, member color background, white initial(s), Inter 600, centered.
Sizes: 24px (inline tags), 34px (home roster rows, top bar), 38px (feed events),
46px (member cards), 56–64px (log screen, invite hero).
Font size ≈ 40% of diameter. Content: user's uploaded avatar image (`object-fit: cover`,
same circle) if present, else **first letter of first name**. An "unknown/you-to-be"
avatar (invite screen) is the same circle with a dashed border, `?` glyph, no fill saturation.

### 5.2 Goal-dot beads (the signature progress element)

Progress toward a per-member target is a horizontal row of circular dots, one per unit of
target. Left-to-right fill order.

- **Filled dot:** solid circle in the member's color. On the member card (large, 26px),
  add a soft same-color shadow: `box-shadow: 0 2px 6px rgba(<member color>, .3)`.
- **Unfilled dot:** transparent with `2px solid var(--line)` border.
- **Next-up dot (behind cue):** if the period is more than ~60% elapsed and the member is
  under target, the first unfilled dot gets a **dashed clay border** (`2px dashed
  var(--clay)`) — a gentle "this one's waiting for you". Only on the current user's own
  rows; partners' unfilled dots stay neutral. (Server computes this; CSS class e.g.
  `.gdot--warn`.)
- **Overflow (count > target):** all target dots filled, then append a compact
  `+N` chip (Inter 11/600, member color text on its soft tint) after the last dot.
  Do not add extra dots.
- **Large targets:** dots work up to ~10. For targets over 10 (monthly cadences), fall
  back to a rounded progress bar (8px tall, `--cream-2` track, member-color fill,
  999px radius) with the same fraction label. Same component API, different renderer.
- Sizes: 16px dots with 5px gap on home cards; 26px dots with 8px gap on the project
  screen's member cards.

Every bead row is paired with a **fraction**: bold count + `/target` in `--ink-2`
(e.g. `**2**/3`). On member cards this fraction is the big Fraunces 32px numeral,
right-aligned, in the member's color, with a tiny caption below (`sessions`, Inter 10.5
`--ink-2`).

### 5.3 Streak badge

Pill: `🔥` emoji + text, Inter 12.5/600. Active streak: text `#9a7415` on `#f9edd4`.
Copy: "🔥 2 weeks strong" (weekly cadence), "🔥 Day 12" (daily). **No streak (0 or 1
period):** show a muted pill — `--ink-2` text on `--cream-2` — reading "New this week"
or omit entirely on tight rows; never show "0 weeks".

### 5.4 Member progress card (project screen centerpiece)

White card, radius 24px, padding 18px, shadow (member level). Structure top-to-bottom:

1. **Header row** (flex, 12px gap): 46px avatar · name block (Fraunces 18 name; if
   current user, a "YOU" tag — Inter 10/700, `--clay` on `--clay-soft`, radius 8px,
   2px 7px padding — sits inline after the name; below the name, Inter 12 `--ink-2`
   goal line: "Aiming for 3 a week") · right-aligned big fraction (5.2).
2. **Goal-dot row** (26px dots).
3. **Footer row** (space-between): streak badge (left) · status line (right, Inter
   12.5/600). Status copy: behind (self) → "1 more to hit your week →" in `--clay`;
   met → "Done for the week ✓" in `--sage`; partner behind → neutral `--ink-2`
   ("1 to go this week") — we never paint the partner's shortfall in alarm color.

**The current user's card is visually distinguished and always first:** border
`1.5px solid var(--clay-soft)` and background
`linear-gradient(180deg, #fdf4ef, #ffffff 60%)`. Partner cards are plain white.
Cards stack vertically, 14px gap, one per member.

### 5.5 Home project card

White card, radius 22px, padding 18px. Structure:

1. **Header row** (space-between): left — Fraunces 19 project name over Inter 12
   `--ink-2` meta line ("Sessions · weekly · with Daniel"); right — one **status pill**
   (11/600): behind → "You're 1 behind" clay-on-clay-soft; all good/streak highlight →
   "🔥 Day 12" gold; both met → "All set this week" sage-on-sage-soft. Exactly one pill,
   priority: your-behind > streak highlight > all-met.
2. **Roster rows**, one per member (11px gap): 34px avatar · name line (Inter 13/600;
   "You" first, always; partner streaks may append "🔥 4" in gold) with right-aligned
   small fraction (`--ink-2`, count bold `--ink`) · 16px goal-dot row beneath.
   For projects with more than 3 members show You + top 2 and a "+2 more" meta line.

Whole card is an `<a>` to the project screen.

### 5.6 Feed event item

List item, no card — feed items sit directly on cream, 14px vertical padding, 22px
horizontal, no separator lines (whitespace separates). Structure (flex, 12px gap):

- 38px avatar (member color).
- Content column:
  - Line 1, Inter 14: "**Daniel** went to the gym" — bold name, verb phrase regular in
    `--ink-2`… actually verb in `--ink-2`: `<b>Daniel</b> <span class="t">went to the gym</span>`.
    The verb phrase is derived from the activity ("went to the gym" style copy comes from
    the template; generic fallback: "logged a session"). Current user renders as "**You**".
  - Timestamp, Inter 11 `--ink-2`: "Tuesday, 6:20pm" (weekday + time within current
    period; older: "Jun 12").
  - **Note bubble** (only if the event has a note): inline-block, `--cream-2` background,
    `1px solid var(--line)`, radius `0 14px 14px 14px`, padding 8px 12px, Inter 13
    `--ink`, 8px top margin. Reads as a tiny speech bubble.
  - **Reaction row** (8–9px top margin, flex, 7px gap):
    - Reaction pill: emoji + count. `--cream-2` bg, `--line` border, radius 16px,
      padding 4px 9px, count Inter 11/600 `--ink-2`. If current user has reacted with
      that emoji: `--clay-soft` background, no border.
    - **Add-reaction affordance:** same pill shape, dashed border, `+` in `--ink-2`.
      Tapping reveals the picker (5.7).

**Nudge feed item** (a nudge rendered in history): 38px circle in gold tint `#f9edd4`
containing an inline-SVG bell in `--gold`, then Inter 13 `--ink-2` text:
"**Daniel** nudged you — “your turn 👀”" (bold name in `--ink`). No reactions on nudges.

### 5.7 Reaction picker

Tapping the `+` pill swaps it (vanilla JS, no navigation) for a horizontal strip of 5–6
tappable emoji in a white pill container (`--card` bg, `--line` border, radius 20px,
padding 6px 10px, emoji 18px, 10px gap): `👏 🔥 💪 🎉 ❤️ 😅`. Tapping one POSTs the
reaction (fetch), then re-renders the reaction row from the response (or full page reload
fallback). Tapping elsewhere closes it. One picker open at a time.

### 5.8 Nudge button

Secondary square-ish button beside the log CTA: 56px wide, full CTA height, radius 18px,
`--card` background, `1.5px solid var(--line)`, containing an inline-SVG bell stroke icon
in `--gold` (20px). Title/aria-label: "Nudge Daniel" (or "Nudge partners" for groups).

- Tapping POSTs a nudge; on success swap the bell briefly for a sage check (JS, ~1.5s)
  and set the disabled state.
- **Rate-limited / disabled state:** `opacity: .45`, `pointer-events: none`, and the
  bell icon in `--ink-2`. A tooltip-ish caption is unnecessary; if space allows on the
  project screen, meta text near the feed may read "You can nudge again tomorrow."
  Server decides availability; template renders the state.

### 5.9 Primary log button

Two forms:

- **Project screen bottom bar:** full-width (minus nudge button) clay button, radius 18px,
  ~52px tall, white Inter 15/600 label with a small inline `+` SVG. Label is
  activity-specific first-person: **"I went to the gym"** (from template), generic
  fallback "Log a session". Clay shadow (see §4).
- **Log screen giant tap target:** 216px circle, centered.
  Background `radial-gradient(circle at 50% 38%, #e8794f, var(--clay))`, white content:
  a thin `+` glyph (64px, weight 300) over a Fraunces 16/600 label "Yes, I went".
  Halo: `box-shadow: 0 16px 40px rgba(217,96,59,.4), 0 0 0 10px #fbe4d8`.
  **Tap feedback (JS):** on pointerdown scale to .96 (transition 120ms); on submit,
  disable immediately and swap label to "Logging…" — then server responds with the
  confirmation state (§6.3b). Respect `prefers-reduced-motion` (skip the scale).

### 5.10 Form fields

- **Text input:** full width, `--card` bg, `1.5px solid var(--line)`, radius 14px,
  padding 14px 15px, Inter 15 `--ink`. Focus: `border-color: var(--clay)`, no outline
  ring beyond it (but keep `:focus-visible` outline for keyboard users:
  `outline: 2px solid var(--clay); outline-offset: 2px`). Placeholder `#b6ab99`.
- **Field label:** Inter 12/600 `--ink-2`, 8–10px below-margin, sentence case
  ("Call it", "What you'll count", "How often").
- **Segmented choice (cadence):** row of equal-width pills, 8px gap; each radius 14px,
  `1.5px solid var(--line)`, Inter 12.5/600 `--ink-2`, padding 11px. Selected: `--clay`
  bg, white text, clay border. Implemented as real `<input type="radio">` +
  `<label>` pairs (radio visually hidden), CSS `:checked + label` styling — works with
  zero JS.
- **Binary choice (duration):** same pattern, two wider options; selected style is
  outline-flavored: clay border, `#fdf4ef` bg, `--ink` text.
- **Stepper (target setting):** centered flex: circular 52px `−` / `+` buttons (`--card`
  bg, `--line` border, clay 24px glyphs) flanking a value block — Fraunces 44/600 clay
  numeral over Inter 12 `--ink-2` caption "sessions / week". Backed by a hidden
  `<input type="number">`; tiny JS increments; clamp at 1 and 99.

### 5.11 Template picker cards

Row of 3 equal-width cards, 10px gap: radius 18px, `1.5px solid var(--line)`, `--card`
bg, centered, padding 14px 8px — emoji 26px over Inter 12/600 name.
Options: 🏋️ "Gym buddy" · 📚 "Study partner" · ✨ "Custom".
Selected: clay border + `#fdf4ef` bg. Also radio-backed (no JS needed for selection);
choosing a template pre-fills the form fields below via a few lines of JS
(name/activity/unit/cadence values embedded as `data-` attributes).

### 5.12 Top nav / header

No persistent tab bar. A minimal top bar per screen, 14px vertical padding, 22px sides:

- **Home:** wordmark left ("Social Pressure." — Fraunces 19/600, clay period), 34px
  current-user avatar right (links to profile/settings).
- **Interior screens:** left — 34px circular icon button (`--cream-2` bg, `--line`
  border, `--ink-2` chevron-left inline SVG) for back; center — optional Inter 14
  `--ink-2` context label (e.g. project name on log screen); right — optional 34px
  overflow icon button (⋯ vertical dots SVG) on the project screen (project settings,
  copy invite link), else an empty 34px spacer to keep the center label centered.
- Log screen uses an ✕ icon in the left slot instead of a chevron (it's a modal-flavored
  flow, cancel returns to project).

### 5.13 PWA safe areas & bottom actions

- `<meta name="theme-color" content="#f7f1e7">` (update the existing base.html value).
- Body bottom padding: `padding-bottom: env(safe-area-inset-bottom)`.
- The project screen's log/nudge **bottom action bar** is sticky
  (`position: sticky; bottom: 0`), padding `12px 18px calc(16px + env(safe-area-inset-bottom))`,
  with a cream fade above it:
  `background: linear-gradient(180deg, rgba(247,241,231,0), var(--cream) 40%)` so feed
  content dissolves beneath it rather than hard-clipping.
- All tap targets ≥ 44px in at least one dimension.

---

## 6. Screens

Common: everything is one column at 390px. Max content width 480px centered for larger
screens (`margin-inline: auto`) — do not build a desktop layout.

### 6.1 Home / project list

Order top-to-bottom:

1. Top bar (wordmark + avatar, §5.12).
2. **Greeting**, Fraunces 26–27: "Morning, Henry." — time-of-day word varies
   (Morning/Afternoon/Evening), first name in `--clay`, closing period in `--ink`.
3. **Greeting subline**, Inter 13.5 `--ink-2` — the pressure hook, computed:
   "Three people are counting on you this week." / with nothing pending:
   "All caught up. Nice." — always one short sentence.
4. **Project cards** (§5.5), most-urgent first (your-behind projects on top, then by
   most recent activity).
5. **"Start a project"** button: full-width, `--ink` bg, `--cream` text, radius 20px,
   16px padding, Inter 14.5/600, leading `+` SVG.
6. **Empty state** (no projects): greeting stays; then a centered block — Fraunces 20
   "Nobody's watching yet." + Inter 13.5 `--ink-2` "Start a project and invite someone
   who won't let you slack." + the same Start button.

Dominant element: the stack of project cards; the greeting is the only display-type moment.

### 6.2 Project screen (THE product)

Order:

1. Top bar: back chevron left, overflow (⋯) right — no center label (title is below).
2. **Hero block** (22px side padding): Fraunces 26 project name; Inter 13 `--ink-2`
   description line ("One session at a time, every week." — project description, or a
   generated line from activity+cadence); below, a **period chip** — inline pill,
   `--cream-2` bg, `--line` border, radius 20px, Inter 12: "📅 This week ·
   **Jun 30 – Jul 6** · 2 days left" (bold dates in `--ink`, rest `--ink-2`).
3. **Member progress cards** (§5.4): current user first with the clay treatment,
   then partners by join order. This block dominates the screen — it is the product.
4. **Feed heading**: Fraunces 17 "The week so far" + Inter 12 `--ink-2` " · 7 check-ins"
   (count = events this period). If the feed spans into previous periods on scroll, a
   simple meta divider line "Last week" (Inter 12 `--ink-2`, 22px padding) separates them.
5. **Feed** (§5.6): events + nudges interleaved, newest first. Show current period fully,
   then paginate/link "Show earlier" (plain text link, clay) — server-rendered pagination.
6. **Sticky bottom action bar** (§5.13): nudge button (56px, left) + primary log button
   filling the rest ("I went to the gym").
7. Feed empty state (new project, no events): in place of the feed — Inter 13.5
   `--ink-2`, centered: "No check-ins yet. First one sets the tone." (If partner hasn't
   joined yet, show instead an **invite reminder card**: white card, "It's just you so
   far." + a "Copy invite link" secondary button — clay text, clay-soft bg, radius 16px.)

### 6.3 Log flow

**(a) Log screen** — reached from the project CTA; must read as < 5 seconds of friction:

1. Top bar: ✕ left, project name center (Inter 14 `--ink-2`).
2. Centered header: 56px current-user avatar; Fraunces 23 **"Did you make it?"**;
   Inter 13 `--ink-2` supporting line with the stakes, bold numbers in clay:
   "Tap once and Daniel finds out right away. You'll be at **3 of 3** — your whole
   week, done." (When not completing the target: "You'll be at **2 of 3** — one more
   after this.")
3. **The giant log circle** (§5.9), vertically centered in remaining space.
4. Under it, Inter 12.5 `--ink-2`: "One tap logs it. That's the whole thing."
5. **Optional note input** at the bottom: standard text input, placeholder
   "Say something? (optional) — “finally did legs”". Filling it does not add steps —
   the circle submits both.

The form is a single `<form method="post">`; the circle is its submit button; note input
included. No confirmation dialog ever.

**(b) Post-log confirmation** — the response page (or swapped main content):

1. Centered vertical stack: 130px circle in `--sage-soft` containing a 58px sage
   check inline SVG; Fraunces 24 **"Nice. That's logged."**; Inter 14 `--ink-2` body
   with bold `--ink` numbers: "**3 of 3** this week — you hit it. Your streak just
   ticked up to **3 weeks**." (Not at target: "**2 of 3** this week — one to go.")
2. **Push receipt pill**: `--cream-2` bg, `--line` border, radius 20px: 24px partner
   avatar + Inter 12.5 `--ink-2` "Daniel just got the notification" (groups:
   "Your partners just got the notification").
3. Buttons row: secondary "Undo" (white bg, `--line` border, `--ink-2` text, radius 16px)
   + primary clay "See the project". Undo POSTs a delete of the just-created event
   (valid ~2 minutes server-side) and returns to the project.

### 6.4 Create project flow

Single page form (server-rendered; template pre-fill via small JS):

1. Top bar: back chevron, center label "New project".
2. Heading, Fraunces 25, two lines: **"Who are you keeping on track?"** + Inter 13
   `--ink-2` "Pick a starting point — you can tweak everything."
3. **"Start from"** — template picker (§5.11). Selecting pre-fills: Gym buddy →
   name "Gym Buddies", activity "Sessions", unit "session", cadence weekly;
   Study partner → "Study Sessions"/"Sessions"/"session"/weekly; Custom → blank fields.
4. **"Call it"** — project name input.
5. **"What you'll count"** — two-column grid (1.4fr/1fr, 10px gap): "Activity" input
   ("Sessions") and "One is a…" unit input ("session"); below, "How often" — cadence
   segment: Daily / Weekly / Monthly.
6. **"Keep going"** — duration binary: "As long as we like" (default) / "Until a date"
   (selecting reveals a native `<input type="date">` styled like a text input — the
   only conditional reveal, done with a 3-line JS toggle).
7. **Plain-language recap card**: `--sage-soft` bg, radius 16px, padding 14px 16px,
   Inter 13 `#3f5a3a` with bold `#2f4a2c`: "You'll be counting **sessions**, one per gym
   trip, **each week**, for as long as you both keep it up. Set your own target once
   you're in." Rebuilt server-side on validation errors; live-updating via JS is
   optional polish, not required.
8. Primary clay full-width button: **"Create & get the invite link →"**. Post-create
   lands on the project screen with the invite reminder card (§6.2.7) prominent.

Creator sets their own target on the project screen the first time (same stepper pattern
in a small card: "How many for you?"), or immediately after create — implementer's choice,
but the stepper component and copy are as in §6.5.

### 6.5 Invite accept screen

Arriving via invite link, possibly logged out (auth first, then return here). Order:

1. Top bar: wordmark only.
2. **Hero**, centered: Inter 13 `--ink-2` kicker "**Daniel** wants you in on this"
   (name bold `--ink`); the **pair graphic** — inviter's 64px avatar and a 64px dashed
   "?" avatar (§5.1) overlapping by ~16px, joined by a small 30px clay heart badge
   (inline SVG heart, white on clay, 3px cream border) sitting between/over them;
   headline Fraunces 24, italic emphasis: "Go to the gym *with Daniel*, even when
   you're not together." (Generated from template/activity; generic fallback:
   "Keep each other on track, one week at a time.")
3. **Details card**: white, radius 20px, rows separated by `--line` hairlines, each row
   space-between — Inter 13.5, key `--ink-2` / value 600 `--ink`:
   Project → "Gym Buddies" · You'll count → "Sessions, weekly" · Daniel's aiming for →
   "2 a week" · Runs → "As long as you like" (or "Until Sep 30").
   For groups list each member's target row.
4. **Target setting**: Fraunces 16 centered "How many for you?" + Inter 12 `--ink-2`
   "Your target is yours — it doesn't have to match Daniel's." + the stepper (§5.10),
   default 3 (or the inviter's target if higher feels wrong — default to inviter's
   target value).
5. Primary clay full-width button: **"Join Gym Buddies"**.
6. Footer meta, centered Inter 11.5 `--ink-2`: "You can change your target later."

---

## 7. Microcopy voice

Rules, with the examples above as canon:

- Second person, present tense, sentence case everywhere (no Title Case, no ALL CAPS).
- Short sentences. One idea each. Contractions always ("You're", "That's", "doesn't").
- Buttons say what happens, in the user's own voice where possible: "I went to the gym",
  "Yes, I went", "Join Gym Buddies", "Create & get the invite link". Never "Submit".
- Numbers users care about are **bold** and, when they're the user's own, clay.
- Behind-state copy encourages, never scolds: "1 more to hit your week →",
  "You're 1 behind" — never "Failed", "Missed", "Overdue".
- Partner framing is togetherness, not rivalry: "with Daniel", "counting on you" —
  never "vs", "beat", "losing".
- Empty states invite action in one line: "Nobody's watching yet."
- Errors are plain and directive: "That name's too long — 100 characters max."

---

## 8. Implementation notes

- **One CSS file** (e.g. `static/core/css/app.css`), hand-written, mobile-first,
  custom properties from §2 at the top. No preprocessor. Keep selectors flat
  (single-class BEM-ish: `.mcard`, `.mcard__foot`, `.gdot--warn`); avoid element-type
  selectors overriding class styles (watch specificity between shared `button` resets
  and `.log-btn` etc. — reset buttons once with a low-specificity rule, style by class).
- **Vanilla JS touchpoints only** (one small `app.js`):
  1. Log button press feedback + disable-on-submit (§5.9).
  2. Reaction picker open/close + fetch POST + row swap (§5.7); full-page fallback if
     fetch fails.
  3. Nudge button POST + temporary check state (§5.8).
  4. Create form: template pre-fill from `data-` attributes; date field reveal.
  5. Stepper increment/decrement.
  Everything must degrade to working full-page form posts without JS except the
  reaction picker (acceptable to require JS there).
- Radio-backed segmented controls and template picker need **no JS for selection**
  (§5.10, §5.11).
- Icons: inline SVG only (chevron, ✕, bell, check, plus, dots, heart — all simple
  stroke paths, `stroke="currentColor"`, so CSS colors them). Emoji for reactions,
  streak fire, and template icons.
- Accessibility floor: visible `:focus-visible` outlines (clay), `aria-label` on
  icon-only buttons, `prefers-reduced-motion` respected on the two animations
  (log-press scale, picker reveal), color is never the only signal (fractions and
  copy always accompany dot colors).
- Update existing `templates/base.html`: theme-color to `#f7f1e7`, add the Google Fonts
  link (§3), replace the inline `<style>` block with the single CSS file link, and
  remove the desktop-oriented `48rem` main width in favor of the 480px mobile-first
  container.
- Reference mockup (for humans, not the implementer): `design/mockups/direction-2.html`.
