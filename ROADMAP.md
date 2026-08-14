# Performance Passport Roadmap

## Current Status

Current release: **v0.31.1 — Pathmark Navigation Hotfix**

Architecture status: **Frozen**

Approved production baseline:

- Coach Home v11 responsive composition
- Jo and Richard athlete imagery
- Shared split-aware session classification
- Treadmill pace-reliability exclusion
- Real-data validation for both athletes
- Production Activity Review using the shared intelligence engines
- Home and Activities production navigation labels
- Intermediate-width Home composition for an expanded sidebar
- Latest Run and Best Runs deep-link to their exact supporting Activity Review
- Athlete and historical activity selection survive Home evidence navigation
- Home's displayed selector and coaching content share one canonical athlete ID
- Progress separates aerobic fitness, training rhythm, race results, threshold
  and durability into honest evidence streams
- Supported heat, humidity/dew point, climbing, wind and trail effects are
  normalised before aerobic and threshold comparisons
- Home and Progress share the same canonical numeric athlete selector
- Race Predictor is a standalone primary destination with the same canonical
  athlete selector
- Any saved goal can be forecast read-only, while six standard race distances
  can be explored without changing the active goal
- Exactly one Active Primary goal drives Home and coaching direction
- Secondary goals are explicit tune-up or benchmark candidates; Future goals
  remain parked with no current influence
- Changing the Primary goal preserves the previous goal as Secondary and never
  silently rewrites the active Training Block
- Training Block Designer starts from each athlete's demonstrated frequency,
  reliable volume, quality rhythm and long-run history
- Running days, session days, long-run day, strength days, volume ceiling and
  recovery constraints are athlete-controlled and persisted
- Generated blocks include safe progression, cutbacks, phase changes, tapering
  and relevant Secondary races without adding hidden intensity
- Buttons now distinguish consequential primary actions from routine choices;
  performance orange is no longer used as the default fill for every action
- Aerobic efficiency uses a browser-safe monthly chart; training rhythm keeps
  total reliable mileage while showing its Easy, Long Run, Session and Other
  composition
- Threshold evidence leads with observed work-phase pace in min/mile and keeps
  the estimated 12°C flat-road equivalent as a separate limited-confidence
  range
- Race cards label both six-month comparison windows and use unambiguous
  improvement/slower wording rather than implying future capability
- Passport Detail composes current physiological boundaries, Progress anchors,
  historical training patterns, personal environmental responses, learned
  workout associations and factual achievements
- Passport pace is shown in min/mile; configured thresholds, historical
  patterns and cautious estimates retain distinct source/confidence language
- Goals now contains an interactive Race Outlook with preset and adjustable
  heat/humidity, ascent, wind exposure and surface conditions
- Selected conditions modify realised race time, range and goal likelihood
  while the underlying capability remains visibly unchanged
- Every condition factor reports its estimated cost and whether the response
  is personalised or still generic

---

## Product Vision

Performance Passport is a coaching-focused running analysis platform. It does
not aim to reproduce Garmin Connect, Strava or Runalyze. Its defining question
is:

> How good was this run, really, compared with my other similar runs after
> accounting for its purpose and conditions?

Deterministic calculations create the conclusion. AI may explain those
calculations, but must not invent them.

---

## Completed Foundations

### Data and athlete identity

- Multi-athlete SQLite database
- Runalyze import, duplicate detection and raw source preservation
- FIT foundation
- Athlete management and `athlete_id` linking
- Richard and Jo validated independently against real historical data

### Coaching intelligence

- Athlete baselines and comparable-session rankings
- Split-aware session classification with confidence safeguards
- Best Runs and Hall of Fame recognition
- Race predictions and coach consensus
- Athlete Passport and learned traits
- Training Blocks, Goals and adaptive weekly coaching
- Journal, Learning and Recommended Next Run foundations
- Treadmill pace-reliability policy across comparative consumers

### Product design

- Pathmark PP identity and Design System v1
- Approved responsive Coach Home
- Active Goal, Performance Intelligence, Race Outlook, This Week, Up Next and
  Best Runs hierarchy
- Desktop Passport/Race Outlook alignment
- Compact-screen Active Goal treatment
- Activity Review hierarchy with a 10px type floor and responsive evidence cards

---

## Completed Sprint — Activity Review

### Coaching question

**How good was this run, really—and why?**

### Delivered

The Activities placeholder is now an evidence-backed review destination.

### Complete slice

- Select and open a real activity.
- Show the shared session classification and confidence.
- Explain the evidence supporting that classification.
- Show moving, elapsed and interruption context.
- Present split/work-recovery structure where source data allows.
- Compare the run only with genuinely comparable sessions.
- Show rank, percentile and the reason it performed well or poorly.
- Make pace-reliability exclusions visible, including treadmill handling.
- Provide a concise coaching interpretation grounded in the calculations.
- Validate the complete screen against representative Richard and Jo sessions.

### Preserved exclusions

- No manual activity editing.
- No route-map rebuild.
- No AI-generated unsupported scoring.
- No new top-level architecture.
- No combined-condition Race Outlook yet.

---

## Completed Sprint — Home Evidence Links

### Product question

**What evidence supports this Home conclusion?**

### Delivered

- Latest Run card and its visible analysis action open the exact activity.
- Featured and category Best Runs open their exact supporting activities.
- View All Runs opens Activity Review for the selected athlete.
- Linked historical activities automatically use the all-time selector window.
- Athlete and activity identity are carried through stable same-app URLs.
- Activity Review validates the linked activity against the athlete's own
  canonical history before rendering it.
- Richard and Jo deep links are covered by real-data and Streamlit handoff
  tests.
- Approved Home structure and rollback previews remain unchanged.

---

## Completed Sprint — Progress Foundation

### Coaching question

**Am I improving—and which parts of my running are changing?**

### Delivered

- A production Progress destination driven by each athlete's real history.
- Conditions-normalised aerobic efficiency over twelve months.
- Generic heat/humidity, climbing, wind and trail allowances scaled by a
  personal response only where the athlete-specific confidence is sufficient.
- Strong, moderate and limited confidence based on comparable sample support.
- Twelve-week training rhythm using active days, moving time and reliable
  distance without pretending consistency itself is fitness.
- Factual 5K, 10K and Half Marathon progress using trusted elapsed results;
  official results and PBs are never environmentally rewritten.
- Threshold evidence based on trusted work phases rather than whole-run pace.
- Durability evidence based on pace decoupling from continuous Long Easy runs,
  with interrupted runs excluded.
- Treadmill time remains useful for rhythm while unreliable treadmill pace and
  distance remain excluded from performance trends.
- Richard and Jo regression coverage plus a Streamlit production-route smoke
  test and canonical athlete-state validation.

---

## Completed Sprint — Goal Hierarchy Foundation

### Product question

**Which goal is actually directing my coaching?**

### Delivered

- One Active Primary goal as the only current coaching direction.
- Secondary goals labelled as tune-ups, benchmarks or supporting outcomes.
- Future goals kept visible with no current coaching effect.
- Complete goals retained as history and restorable as Future.
- Explicit promotion, role changes, editing and lifecycle actions.
- Previous Primary preserved as Secondary when another goal is promoted.
- Existing Training Block preserved and flagged for review after a Primary
  change rather than being silently regenerated.
- Block creation offered only from the Primary goal.
- Richard and Jo validated independently against their current saved goals and
  block links.

---

## Completed Sprint — History-Led Training Blocks

### Product question

**How should this athlete's real history become a safe, realistic block?**

### Delivered

- Recent running frequency, hours, reliable mileage, quality load and long-run
  pattern composed into a transparent history profile.
- Primary goal as the sole block direction, with relevant Secondary races
  placed as tune-ups without adding hidden quality load.
- Athlete-controlled running, long-run, session and strength days, weekly
  mileage ceiling, race substitution and recovery/life note.
- Base, Build, Specific, Taper and Race phases with cutbacks and cautious volume
  progression.
- Back-to-back hard-day, unsupported session-frequency and excessive-volume
  warnings.
- Persisted evidence snapshot, preferences and complete week/day shape using
  database schema v10.
- Independent Richard and Jo real-data coverage plus pure generator,
  persistence and responsive UI contracts.

---

## Completed Sprint — Operational Block Coaching

### Coaching question

**How should the saved block respond to what the athlete actually completes?**

### Delivered

- Current saved week matched to real running activities by date and training
  purpose, preferring athlete-relative Performance Recognition evidence.
- Reliable completed distance compared with planned mileage; treadmill or
  otherwise unreliable runs count by time without invented distance.
- Explicit Complete, Different, Missed, Extra, Planned and Today day states.
- Planned running-day, quality-commitment and long-run completion summaries.
- Next incomplete commitment promoted into Home and Recommended Next Run.
- Recovery protection when actual hard running makes the next saved hard day
  unsafe, while leaving athlete-approved days and volume ceiling unchanged.
- Responsive operational evidence and suggestion surface in Training Blocks.
- An explicit not-yet-active message when the current proposal has no persisted
  custom design, including the exact save/update action required.
- Clickable week cards that select, highlight and open their seven-day shape
  directly below the timeline while preserving Next Run's prescription role.
- Same-app week navigation carries the Training Blocks route, athlete ID and
  week number, then consumes that URL state so normal sidebar navigation resumes.
- Real-data tests derive the expected block name and date state from the current
  database, while continuing to enforce athlete separation and goal/block links.
- Pure matching, real Richard long-run recognition, Home/Next Run fallback and
  responsive UI regression coverage.

---

## Completed Sprint — Pathmark Navigation

### Product question

**Can every destination feel like one coherent Performance Passport product?**

### Delivered

- The approved Pathmark asset replaces the temporary inline sidebar mark.
- Running, analysis, planning and management destinations share one canonical
  route state, eliminating simultaneous selections and the visible `None` item.
- Clear route-group spacing provides information hierarchy without creating
  separate navigation controls or fragile overlaid labels.
- Quiet waypoint dots and a warm-paper, ink and orange-edge active treatment
  improve scanning while preserving keyboard focus and compact layouts.
- Existing activity and Training Block deep links still restore the requested
  route and athlete; legacy management state is migrated once.
- Regression tests protect the real asset, route order and visual contract.

---

## Following Priorities

1. Deliberate Block Review allowing suggested changes to be accepted, deferred
   or rejected with an audit trail; never silently mutate future weeks.
2. Saved course/weather profiles and route-specific Race Predictor evidence.
3. Login-led athlete identity and Coach Mode athlete switching.
4. Direct Strava/Garmin integration through the canonical activity model.

---

## Development Rules

Every sprint must:

- Start from a clean Git status in Richard's real repository.
- Use the agreed architecture.
- Build one feature to completion.
- Keep changes small and testable.
- Validate calculations against the real current database.
- Preserve Richard and Jo as independent athletes.
- Explain any measurement exclusions and confidence limits.
- Update tests and documentation.
- Commit only after successful testing.
