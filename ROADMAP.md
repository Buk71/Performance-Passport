# Performance Passport Roadmap

## Current Status

Current release: **v0.37.1 — Garmin Activity Matching Hotfix**

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
- Garmin FIT and nested export-ZIP import with original-file preservation
- Exact FIT duplicate detection and conservative Runalyze enrichment
- FIT session, lap, device and record-coverage evidence in the canonical
  activity contract
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

## Completed Sprint — Block Review and Deliberate Adaptation

### Product question

**When real training changes the safest next step, how can Performance Passport
recommend a change without taking control away from the athlete?**

### Delivered

- The first review trigger reuses Operational Block evidence when an unexpected
  demanding run sits within one day of the next saved hard commitment.
- Approved and proposed commitments remain visible side by side.
- Accept, Defer and Reject each append a dated audit event with an optional
  athlete reason; the latest decision controls the result.
- An accepted recommendation overlays one future day at read time. The original
  `training_block_designs.plan_json` is never modified.
- A later Defer or Reject removes a previously accepted overlay while preserving
  the earlier decision history.
- Training Blocks, Home and Adaptive Coach/Next Run consume the same effective
  Operational Week contract.
- Schema v11 adds `block_review_actions` without changing imported activities,
  existing goals or saved Training Block designs.
- Regression coverage protects persistence, athlete/block scoping, original
  plan preservation, operational integration, responsive UI and Jo's real
  upcoming saved block.

---

## Completed Hotfix — Training Blocks Readability

- Increased the rationale and supporting evidence type scale to use the clear
  space already available inside desktop cards.
- Enlarged week phase labels, mileage, emphasis, dates, session counts and the
  daily-shape action while retaining the four-card desktop grid.
- Applied the same readable hierarchy to selected daily shape, Operational
  Block Coaching and Deliberate Block Review surfaces.
- Preserved all existing container breakpoints, coaching logic, persistence and
  navigation behaviour.
- Added a regression test enforcing the new minimum supporting-text sizes.

---

## Completed Sprint — Weekly Fuel Planner

### Product question

**How should each athlete fuel the training they have deliberately approved?**

### Delivered

- A standalone Fuel Planner reads the next available week from the active,
  saved Training Block and accepted Block Review overlays.
- Rest/recovery, Easy, Quality and Long run/race demand is derived from the
  saved session purpose without writing back to training.
- Every athlete has an independent profile covering dietary style, servings,
  allergies/intolerances, dislikes, cooking time, budget and batch cooking.
- Omnivore, pescatarian, vegetarian and vegan are first-class filters. Vegan
  athletes retain at least four complete curated recipes in every meal slot
  before personal exclusions are applied.
- Two date-rotated choices are offered for breakfast, lunch, dinner and recovery
  snack on each day, with optional per-serving calorie, carbohydrate and protein
  estimates.
- Saved choices generate one categorised ingredient roll-up with combined
  quantities, optional pantry staples and a downloadable CSV.
- Household mode combines every athlete who deliberately saved choices for the
  same week; independent lists remain the default.
- Schema v12 stores profiles and meal selections without changing imported
  activities or the athlete-approved Training Block.
- Real-data validation confirms Jo's saved upcoming week and honestly gates
  Richard until his generated Training Block is saved; real Richard history
  still validates the downstream composition independently.

### Preserved boundaries

- No meal can change mileage, weekdays, session purpose or Next Run.
- Allergens are a filtering aid, not a substitute for checking product labels
  and cross-contamination warnings.
- Supplements are not automatically prescribed.
- Nutrition estimates are planning support, not diagnosis or treatment.

---

## Completed Hotfix — Dietary Choice Balance

- Omnivore no longer means unrestricted rotation through a catalogue whose
  larger plant-based set could dominate the visible choices.
- Every Omnivore lunch and dinner now leads with a rotating meat or fish recipe
  and pairs it with a complete vegetarian or vegan alternative.
- Pescatarian lunch and dinner use the same deliberate pattern with fish first
  and a plant-based alternative second.
- Breakfast and recovery snacks remain naturally vegetarian/vegan rather than
  adding token meat to satisfy a label.
- Six additional salmon, cod, turkey and lean-beef recipes prevent repetitive
  chicken-and-tuna defaults.
- Personal diet, allergy, dislike, cooking-time, budget and batch-cooking
  filters still take priority; a safe compatible fallback replaces either side
  when necessary.

---

## Completed Sprint — Performance Passport Welcome

### Product question

**Can the first screen communicate why Performance Passport deserves to exist
before asking someone to navigate the product?**

### Delivered

- A full-screen branded entry using the approved Pathmark asset, motto, ink,
  warm paper, performance orange, progress green and route/topographic motifs.
- A clear Understand → Plan → Adapt story rather than another athlete dashboard.
- Product-preview cards describe capability, direction, Race Day, latest-run
  interpretation, Training Blocks and Fuel Planner without exposing real names,
  results or training data.
- One accessible entry action opens the unchanged app for the browser session.
- Existing activity and Training Block deep links bypass the welcome screen and
  preserve their exact athlete/evidence request.
- The sidebar is absent on the welcome surface and returns unchanged after
  entry; no new parallel navigation state was introduced.
- Desktop, intermediate and mobile compositions plus reduced-motion behaviour
  are protected by regression tests.
- The sidebar open/close control now has explicit warm-paper, ink and orange
  contrast under dark browser/operating-system colour schemes.

### Preserved exclusions

- No login or self-selected athlete/coach role.
- No private athlete information on the opening page.
- No hosting, database or authentication migration.
- No changes to coaching calculations or the production Home dashboard.

---

## Completed Sprint — Premium Product Story

### Product question

**Can the welcome page communicate the breadth of Performance Passport without
becoming a crowded feature catalogue or claiming unfinished integrations?**

### Delivered

- An editorial “performance intelligence layer” proposition beneath the
  established opening hero.
- Eight premium capability stories covering the living Passport, athlete-
  relative run quality, environmental context, Best Runs, Race Intelligence,
  Training Blocks, deliberate adaptation and Fuel Planner.
- One connected-week loop showing how run evidence feeds learning, planning,
  athlete-approved adaptation and recovery support.
- A trust panel that makes real history, transparent confidence and athlete
  agency visible parts of the product proposition.
- A clearly labelled roadmap for Garmin activity delivery, workouts sent back
  to the watch and secure athlete/coach access.
- A second accessible entry action after the deeper product story.
- Responsive two-column and single-column compositions for the new content.

### Preserved exclusions

- Roadmap capabilities are explicitly separated from current functionality.
- No athlete data, names or real results are exposed.
- No changes to routing, database schema, coaching calculations or Home.
- No Strava integration claim is made under the current restrictive API terms.

---

## Completed Hotfix — Welcome Alignment

- The Athlete Passport preview is now level rather than using an editorial
  one-degree rotation.
- The fixed Streamlit header is hidden only on the welcome surface, removing
  the top border that could overlap the Pathmark brand in Safari.
- The real Pathmark asset has a larger presentation area and remains fully
  visible rather than being clipped by its wrapper.
- Entry routing, deep links, product content and every coaching calculation are
  unchanged.

---

## Completed Hotfix — Welcome Card Spacing

- The three supporting cards now sit behind a deliberate 18px gutter rather
  than touching the main Athlete Passport preview.
- The same spacing is preserved at desktop, intermediate and mobile widths.
- Card sizing, hero alignment, routing and product content are unchanged.

---

## Completed Sprint — Athlete Welcome Entry

### Product question

**Can the welcome page open the correct athlete immediately while preserving
one canonical selection contract across the product?**

### Delivered

- Real athlete records appear as premium “Choose your Passport” entry cards.
- Each entry carries the athlete's numeric ID into the established session
  selection before Home is mounted.
- A stale athlete display name is cleared so every page derives it again from
  the canonical ID.
- The temporary entry query is consumed after selection; activity and Training
  Block deep links retain their existing behaviour.
- The closing welcome action returns to the athlete choice rather than opening
  an ambiguous default athlete.
- Two-column desktop and single-column mobile presentations are protected by
  the existing welcome regression suite.
- Richard and Joanne were verified against the real current database.

### Preserved boundary

This is a local-development routing convenience. It is not authentication and
does not grant or restrict access. Hosted commercial access still requires
secure identity, athlete permissions and a durable database.

---

## Current Sprint — Garmin FIT Import

### Product question

**Can a new athlete bring genuine Garmin history into the existing Passport
without losing detailed source evidence or duplicating a Runalyze activity?**

### Delivered

- Individual FIT, multi-file and recursively nested Garmin export-ZIP
  discovery.
- FIT validation plus session, lap, device, event, workout and record-coverage
  extraction.
- Original FIT binaries retained outside Git as the immutable source of truth.
- Running-only import by default, explicit athlete confirmation and a complete
  preview/import audit.
- Exact repeat-file protection and conservative same-time/distance/duration
  matching that enriches an existing Runalyze row.
- No schema or architecture change; future Garmin Activity API delivery can
  reuse the same ingestion contract.

### Real-data completion gate

- Run the automated suite in Richard's project environment.
- Import one genuine Garmin FIT into a deliberate test athlete, inspect its
  Activity Review and repeat the same import to verify duplicate handling.
- Import Paul's Garmin history only after that small real-file check succeeds.

---

## Completed Hotfix — Garmin Activity Matching

- Garmin Connect's activity ID is read from its export filename and matched
  first against the Runalyze `externalId` retained in raw source data.
- Whole-hour timezone differences can no longer defeat an otherwise exact
  distance-and-duration match.
- Re-uploading a file mistakenly added by v0.37.0 enriches the original
  Runalyze row and safely removes the extra Garmin row, retaining linked
  derived evidence.
- Richard's 5 August 2026 Blizard session (`23865797605`) validates the real
  identity contract: the Runalyze title and row remain canonical while FIT
  detail is attached to them.

## Completed Hotfix — Garmin Environmental Evidence

- Enriching a Runalyze activity retains its weather-corrected temperature and
  elevation instead of replacing them with device temperature and raw
  barometric ascent from FIT.
- The FIT values remain preserved as detailed source evidence.
- Re-uploading an exact FIT duplicate repairs environmental fields previously
  overwritten by v0.37.1 without adding or deleting an activity.

---

## Following Priorities

1. Validate the Garmin importer with Paul as a third real athlete, including
   a repeat import and a hands-off journey from welcome to next action.
2. Fuel Planner preparation instructions and deliberate meal swaps while
   retaining the saved-selection and shopping-list audit contract.
3. Additional deliberate review types for missed weeks and sustained volume
   disruption, reusing the v0.32 audit and overlay contract.
4. Saved course/weather profiles and route-specific Race Predictor evidence.
5. Approved Garmin Activity API transport through this canonical FIT contract.
6. Hosted PostgreSQL, login-led athlete identity and authorised Coach Mode once
   the product's functional scope is ready for a commercial pilot.

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
