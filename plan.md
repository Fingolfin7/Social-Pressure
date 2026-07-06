# Social Pressure — Project Plan

*Drafted 2026-07-04. Status: V1 built and deployed on Render. This document is now a
historical record of the plan plus the roadmap for what's next (V1.5 outcomes layer,
V2 dead-partner mechanics). See [README.md](README.md) for current status.*

## Concept

An accountability-partner app. Users define arbitrary goals/projects (gym, math study,
Czech practice), invite partners into each project, and mutual progress visibility plus
real-time push notifications provide the social pressure that keeps everyone on track —
the functional equivalent of having a friend physically go to the gym with you.

Core thesis: **the human element is the feature; everything else is plumbing.** Habit
apps fail by replacing the human with gamification. This app connects you to one.

## Design principles (decided during brainstorming)

- **The project is the relationship container.** No friends list, no follower graph.
  Partners are per-project (your Czech partner ≠ your gym partner). Privacy scoping
  falls out of the structure: project members see that project, nothing else.
- **Atomic unit is a pair; groups are supported.** Membership is a many-to-many —
  works at n=2 and n=4+. No hard cap in the schema; soft cap (~5–8) in the UI.
  Small groups soften the dead-partner problem; large groups dilute pressure into a feed.
- **Bring your own partner (v1).** Stranger matching is a v2 marketplace problem.
  V1 users invite people they already know, via link.
- **Two-layer metric model:**
  - **Activities (inputs / lead measures)** — countable, volitional events
    ("gym sessions", "problem sets"). Shared definition per project
    `(name, unit, cadence)`, **per-member target** (you: 3/week, beginner friend: 2/week).
    ALL social pressure attaches here: streaks, nudges, comparisons, push notifications.
  - **Outcomes (lag measures)** — personal trend measurements (weight, mile time).
    Per-member value, direction, and target. Displayed as your own trend line only.
    **Never compared between members, never nudged.** Resolves the
    gain-weight/lose-weight partner case: the shared thing is the activity;
    outcomes point wherever each member needs.
  - These are different data kinds: activity logs are *events* (counted per period);
    outcome entries are *measurements* (latest value / trend). Do not unify them
    into one table.
- **Flexibility in the data model, opinions in the UI.** Arbitrary metrics are the
  engine; onboarding shows opinionated templates ("Gym buddy", "Study partner")
  with custom as the escape hatch.
- **Projects choose fixed end date or indefinite** at creation.
- **No in-app chat.** Users have WhatsApp. Nudge button (rate-limited) + emoji
  reactions on logged events cover the social texture.
- **Push, not pull.** Pressure that only exists when you open the app isn't pressure.
  Real-time notification when a partner logs is the product.

## Known hard problem

**The dead-partner problem:** when one member stops logging, the other's motivation
collapses. V1 handles only the basics (reminders); real mechanics (pause states,
gone-quiet handling, archiving) are v2. Dogfooding at n=2 exists largely to learn
about this.

## Roadmap

### V1 — MVP: the loop works (log → partner sees → pressure) ✅ shipped

Feature test: does it serve the core loop? If not, cut it. All of the following are
built and deployed:

- Accounts: email + password, bare profile (name, avatar).
- Create project: name, one activity (name, unit, cadence), fixed end date or
  indefinite, a few pre-fill templates + custom.
- Invite by link (no user search or directory).
- Per-member target, set on join.
- Log an event: one tap, optional note. Under five seconds of friction.
- Project screen (THE product): each member's count vs. their target this period,
  streak, simple history.
- Real-time web push: partner-logged notification; end-of-period behind-schedule
  reminder. Event-driven pushes, no websockets; in-app view refreshes on load.
- Nudge button (rate-limited) + emoji reactions on logged events.
- PWA: manifest, service worker, installable.

Explicitly cut from v1: outcomes, chat, stranger matching, verification,
framing settings, any groups UI beyond a member list (schema supports n members
from day one).

### V1.5 — Outcomes layer

- Personal outcome measurements: per-member definition/direction/target,
  trend chart on own view only.
- Weekly digest notification ("your week: 3/3, Daniel 2/3, weight −0.4kg") —
  the Sunday-night retention pull.
- Notification preferences (real-time vs. digest-only).

### V2 — the rest, rough priority order

1. Dead-partner mechanics: pause states, gone-quiet handling, project archiving.
2. Competitive vs. supportive framing as per-project setting; mini-leaderboard
   for groups of 3+ (competition motivates gym, backfires for weight/mental-health
   goals — hence a setting).
3. Stranger matching: profiles, interests, discovery. Only after retention with
   known partners is proven.
4. Verification: photo check-ins, then integrations (Strava, screen time).
   Required *for* stranger matching — honor system doesn't survive strangers.
5. **Capacitor native wrapper** — the iOS escape hatch (see below).
6. Monetization, if ever.

## Stack

- **Django 5**, server-rendered templates, **vanilla JS** (no React, no jQuery).
  Rationale: app state lives on the server (who logged what, streaks, targets);
  client needs a log button, nudges, reactions, and a service worker — a few
  hundred lines of vanilla JS, no build step, no parallel JSON API to design.
  If partial-page updates start to hurt, the upgrade path is **htmx**, not React.
- **Web push**: `pywebpush` + VAPID, service worker.
- **DB**: SQLite locally → Postgres when deployed.
- **No Channels, no Celery, no build tooling** for v1. Thread or cron-style job
  sends notifications at this scale.
- Charts (v1.5): Chart.js or similar via script tag.

### Platform assumption & the iOS caveat

**Assuming Android for now** — web push works friction-free there.
iOS web push (16.4+) only works when the PWA is installed to the home screen;
onboarding must walk iPhone users through Add to Home Screen, and it should be
tested on a real iPhone before iPhone users are invited. If PWA push proves too
flaky or install friction kills adoption, **Capacitor wraps the existing
Django-served web app in a native shell with real native push — no rewrite.**
This escape hatch is what makes betting on PWA safe.

## Borrowing from AutumnWeb (`Python/AutumnWeb`)

Copy at implementation level (plumbing, not product):
- `users` app: auth backends, email login, signup/profile templates.
- `core/pwa.py`: manifest endpoint + icon/service-worker wiring (battle-tested PWA setup).
- `get_period_bounds` / period utilities in `core/utils.py`: timezone-aware period
  boundaries — foundation for cadence targets and streaks.
- Render deployment shape (render.yaml patterns, free-tier lessons).

Borrow conceptually only:
- `Commitment` model = ancestor of the activity-target idea (target per period,
  am-I-meeting-it, period rollover). Read for lessons; do NOT copy — its four nullable
  one-to-ones + include/exclude M2Ms are the "flexibility in schema without opinions"
  trap this project must avoid.

Do not borrow:
- Core data model (Projects/SubProjects/Sessions/Context/Tag): single-user,
  duration-based hierarchy. Social Pressure is multi-user, event-based, flat.
  Risk: becoming "Autumn with friends." Autumn measures time spent; Social Pressure
  counts things done.
- Charts machinery. V1 needs a progress bar and a streak number.

Note: the heart of Social Pressure (web push, invite links, multi-user visibility,
nudges) has no analog in AutumnWeb — the interesting work is genuinely new.

## Open questions

- Notification rhythm details: exact triggers, quiet hours, rate limits on nudges.
- What "project ended" looks like for fixed-duration projects (summary screen? renew prompt?).
- Streak definition across cadences (weekly cadence: does the streak count weeks?).
