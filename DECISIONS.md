# Performance Passport Decisions Log

This document records major technical and project decisions.

Routine development belongs in ROADMAP.md.

Architecture belongs in ARCHITECTURE.md.

---

# Decision 001

**Date**
28 June 2026

## Architecture Freeze

### Decision

The project architecture is frozen following Sprint 2.1.

```
Performance-Passport/

app.py
config.py

core/
ui/
database/
uploads/
assets/
tests/
```

No new folders or architectural changes will be introduced without an explicit refactoring sprint.

### Reason

Maintain stability.

Avoid architecture drift.

Git should always provide a clean recovery point.

---

# Decision 002

**Date**
28 June 2026

## Development Workflow

### Decision

Every sprint will:

- Have a version number.
- Start from a clean Git status.
- List changed files.
- Provide complete replacement files whenever practical.
- Explain architectural decisions.
- Test before committing.
- Recommend a Git commit after testing.

### Reason

Maintain consistency and minimise mistakes.

---

# Decision 003

**Date**
28 June 2026

## Athlete Management Before Dashboard

### Decision

Athlete management will be completed before dashboard development.

### Reason

Most future functionality depends upon reliable athlete profiles.

Completing athlete management first provides a stronger foundation.

---

# Decision 004

**Date**
28 June 2026

## Activities Will Link Using athlete_id

### Status

Accepted

### Decision

Activities will ultimately reference athletes using:

```
athlete_id
```

rather than

```
athlete_name
```

### Reason

Benefits include:

- Reliable multi-athlete support.
- Multiple import sources.
- Simpler database queries.
- No problems caused by name changes.
- Cleaner dashboard implementation.

Implementation took place during Sprint 2.3.

---

# Decision 005

**Date**
28 June 2026

## Documentation Is Part Of The Project

### Decision

The repository documentation is considered part of the software.

Current project documentation consists of:

- ARCHITECTURE.md
- ROADMAP.md
- DECISIONS.md
- README.md

### Reason

Project decisions should not depend upon conversation history.

Documentation becomes the long-term source of truth.

---

# Decision 006

**Date**
30 June 2026

## Coaching Engine Foundation

### Status

Accepted

### Decision

Introduce a dedicated coaching calculation module:

```
core/coaching.py
```

This module will become the single location for deterministic coaching calculations.

Dashboard pages and future features should consume these reusable functions rather than implementing calculations directly.

The initial implementation includes:

- Distance conversion helpers
- Pace calculations
- Pace formatting
- Support for both metric and imperial units
- RunProfile dataclass
- Training session classification
- Placeholder for future Aerobic Efficiency calculations

### Reason

Performance Passport is intended to become a coaching platform rather than a statistics dashboard.

Future features including:

- Best Ever Easy Run
- Heat Adjustment
- Durability
- Fatigue
- Race Readiness
- Passport Score

all require a common, reusable calculation layer.

Building this foundation now avoids duplicated logic throughout the application while preserving the existing architecture.

No database changes were required.

No architecture changes were required.

---

# Decision 007

**Date**
30 June 2026

## Coaching Pipeline

### Status

Accepted

### Decision

Performance Passport will evaluate activities using a layered coaching pipeline rather than calculating a single score directly.

The coaching pipeline is:

```
Activity
    ↓
Run Profile
    ↓
Training Session Classification
    ↓
Athlete Baseline
    ↓
Percentile Ranking
    ↓
Context Adjustments
        • Heat
        • Elevation
        • Terrain
        • Fatigue
        • Durability
    ↓
Passport Insight
```

Best Ever Easy Run will be built on top of this coaching pipeline rather than using a standalone algorithm.

### Reason

Coaches do not compare every run against every other run.

They first identify the type of session, then compare it against similar sessions performed by the same athlete.

This approach allows Performance Passport to explain:

- How good a run was.
- Why it was good.
- How it compares with the athlete's own historical performances.

The percentile ranking engine will become the foundation for future coaching features including:

- Best Ever Easy Run
- Benchmark Workouts
- Heat-adjusted performance
- Durability
- Fatigue
- Race Readiness
- Passport Score

This creates a transparent, deterministic and explainable coaching model while remaining simple to extend as additional data becomes available from FIT file imports.

---

# Decision 008

**Date**
30 June 2026

## Build Coaching Before AI

### Status

Accepted

### Decision

All coaching intelligence will be implemented as deterministic, explainable calculations before any AI-generated coaching commentary is introduced.

AI will never invent scores or training conclusions.

Its role will be to explain the outputs of the coaching engine in natural language.

### Reason

The credibility of Performance Passport depends on runners understanding why a run has been assessed in a particular way.

Transparent calculations are easier to test, validate and improve over time.

This approach also ensures that future AI explanations remain grounded in measurable evidence rather than subjective interpretation.
---

# Decision 009

**Date**
5 July 2026

## Timing Rules

### Status

Accepted

### Decision

Performance Passport will use different time fields depending on the purpose of the analysis.

Use **elapsed time** for:

- PBs
- Fastest 1k / 5k / 10k / half marathon / marathon
- Distance records
- Race performance metrics

Use **moving time** for:

- Training sessions
- Easy runs
- Threshold runs
- Long runs
- Performance Passport coaching analysis
- Coaching metrics
- Best Ever Easy Run / Threshold / Long Run analysis

### Principle

Performance metrics use elapsed time.

Training quality metrics use moving time.

### Reason

Race and record performance should reflect the full time taken to complete the distance.

Training quality analysis should focus on the active running portion of the session so that stops, pauses and non-running interruptions do not distort coaching insight.

---

# Decision 015

**Date**
12 August 2026

## One Shared Split-Aware Session Classification

### Status

Accepted

### Decision

The explainable classifier in `core/session_intelligence.py` is the source of
truth for activity type across Performance Recognition, Latest Run and Hall of
Fame.

Recorded workout structure outranks whole-activity averages and generic source
titles. In particular:

- work/recovery splits, manual-lap boundaries and stopped-watch recovery gaps
  identify structured workouts;
- downstream features only treat the shared result as authoritative from 70%
  classification confidence; ambiguous older patterns retain conservative
  fallback handling;
- an average heart rate below LT1 cannot turn a structured workout into an easy
  run;
- explicit workout titles provide a fallback when detailed splits are absent;
- titles and summary averages remain supporting evidence, not separate
  downstream classifiers;
- whole-run aerobic awards exclude structured workouts because stopped
  recoveries can distort moving pace and average heart rate.

### Reason

Activity 3177 on 13 August 2025 contained a progressive warm-up, strides and a
1–2–3–4–5–4–3–2–1 ladder at 5K pace. Its 35 recorded segments clearly showed a
structured session, but Hall of Fame independently treated its generic
Runalyze title and average heart rate as evidence of an easy run.

A single evidence hierarchy prevents the same activity receiving contradictory
labels in different parts of the product and creates one explainable place to
improve classification as FIT, Garmin and Strava data become richer.

---

# Decision 016

**Date**
12 August 2026

## Treadmill Pace Reliability

### Status

Accepted

### Decision

Treadmill sessions remain valid training activities, but their recorded
distance and pace are not used for comparative performance intelligence.

Explicitly identified treadmill, indoor-running and virtual-running activities
are excluded from:

- personal best and fastest-distance records;
- Hall of Fame and Best Runs awards;
- pace-efficiency calculations;
- athlete-relative pace rankings and pace-derived trends;
- environmental pace-response comparisons.

They remain eligible to contribute trustworthy evidence including:

- completed-session history;
- moving duration and training frequency;
- heart rate and time-based training load;
- workout structure where splits or laps support it;
- continuity, subject to the normal source-data rules.

Session classification and measurement reliability are separate decisions. A
treadmill activity may still be correctly classified as Easy, Recovery or a
Structured Workout even though its distance and pace are excluded from
comparison.

### Reason

Richard's treadmill pace is usually inaccurate. Activity 3428 on 11 January
2026 was therefore appearing as Best Easy Run primarily because unreliable
treadmill distance and pace produced an artificially strong efficiency score.
Keeping the activity while excluding only the unreliable measurements protects
training history without contaminating records or coaching intelligence.


## Decision 014 – Training Blocks as the Version 1.0 Organising Context

**Status:** Accepted

Performance Passport will organise coaching around Training Blocks.

A Training Block is a purposeful period of training such as Base, 10K, Half
Marathon, Speed Development or Recovery.

Goals belong to Training Blocks rather than replacing them.

The active Training Block provides context for future Decision Engine,
Recommended Next Run, Dynamic Plan, Block Hall of Fame, Block Review and Coach
Mode features.

This preserves the architecture freeze: the feature is implemented through
`core/training_blocks.py`, the existing database module and a UI page. No new
top-level architecture is introduced.

---

# Decision 017

**Date**
12 August 2026

## Approved Home Becomes the Production Coach Entry Point

### Status

Accepted

### Decision

The v11 responsive Home composition is the approved production Home baseline
for version 0.22.0.

`app.py` routes the existing Coach navigation item to `ui/home.py`. The
approved preview versions remain in the repository as visual rollback history
while the production wrapper preserves their tested calculations and layout.

The locked Home hierarchy is:

1. Athlete identity and Active Goal.
2. Athlete Passport and Performance Intelligence.
3. Race Outlook aligned with the Passport baseline.
4. This Week and Up Next.
5. Best Runs.

The current athlete selector is temporary. A future authenticated athlete view
will infer identity from login, allow Active Goal to span the page and move
athlete switching into Coach Mode navigation.

The future detailed Race Outlook will support combined selectable conditions
such as Hot, Hilly, Trail and Windy. Combined effects must use personal athlete
responses rather than simply adding independent penalties.

### Reason

The Home now expresses Performance Passport's differentiator in the correct
order: identity, goal, interpretation, race outlook, coaching action and
historical evidence. It has been visually approved at desktop and compact
widths and verified against Richard's and Jo's real data.

---

# Decision 018

**Date**
12 August 2026

## Activity Review Separates Classification, Reliability and Recognition

### Status

Accepted

### Decision

Activity Review is the athlete-facing evidence layer for one session. It joins
the existing shared engines without creating new competing calculations:

- Session Intelligence decides what kind of activity it was and states its
  confidence.
- Activity Reliability decides whether recorded distance and pace are suitable
  for comparison.
- Split Intelligence reconstructs supported work, recovery and boundary
  structure.
- Performance Recognition ranks the activity only inside its athlete-relative
  comparable category.

The UI must expose conflicts and confidence thresholds. A moderate possible
race classification, for example, does not silently override the conservative
comparison category below the shared 70% confidence floor. Stopped-watch gaps
may be identified, but their missing duration must not be invented.

### Reason

Classification and performance quality answer different questions. Keeping
them separate prevents a structured session being called Easy because of its
whole-run average, prevents treadmill pace entering outdoor rankings, and lets
athletes see exactly which evidence supports each conclusion.

---

# Decision 019

**Date**
12 August 2026

## Home Evidence Links Use Stable Activity Review URLs

### Status

Accepted

### Decision

Home evidence cards link to Activity Review through a small same-app URL
contract carrying the destination, athlete ID and optional activity ID.

The URL selects navigation state only. Activity Review remains responsible for
validating that the requested activity belongs to the requested athlete before
it is displayed. Linked historical Best Runs switch the selector to All Time,
and the navigation parameters are consumed once so normal manual selection can
resume immediately.

The production wrapper adds links around the approved Home markup. Locked
preview modules and all coaching calculations remain unchanged.

### Reason

Home conclusions should be directly auditable without duplicating Activity
Review or introducing a second routing architecture. Stable URLs also preserve
browser behaviour, provide accessible links and create a future-compatible
entry point for shared activities while keeping athlete isolation inside the
canonical review layer.

---

# Decision 020

**Date**
12 August 2026

## Progress Separates Fitness Signals and Normalises Comparable Pace

### Status

Accepted

### Decision

Progress will not collapse different longitudinal questions into a single
opaque score.

- Aerobic fitness compares pace relative to heart rate after conservative
  normalisation for supported heat, humidity/dew point, climbing, wind and
  trail effects. High-confidence personal response may scale the corresponding
  generic allowance.
- Training rhythm reports running days, moving time and reliable distance. It
  is consistency context, not a claim of improved fitness.
- Race progression uses trusted factual elapsed results. Conditions may be
  shown as context but never rewrite an official result or PB.
- Race direction compares the best trusted result in the recent 180 days with
  the best result from days 181–365. Both windows must be labelled; the change
  is historical progress and must not read like predicted future improvement.
- Threshold progression uses trusted work-phase pace, not whole-run pace that
  mixes warm-up and recovery.
- The threshold headline is the observed work-phase pace in the athlete-facing
  unit. Conditions-normalised pace remains useful for like-for-like trend
  calculation, while a displayed 12°C flat-road equivalent is a cautious range
  and not a confirmed physiological threshold.
- Durability uses within-run pace decoupling from continuous Long Easy runs and
  excludes materially interrupted sessions.
- Missing or incomparable data reduces confidence. It is never silently filled
  or converted into certainty.
- Treadmill moving time may support rhythm; unreliable treadmill distance and
  pace remain excluded from comparative performance evidence.

The calculation layer lives in `core/progress.py`; `ui/progress.py` presents
its typed summary. Both Progress and Home use the canonical numeric athlete
selector.

### Reason

An athlete can become more consistent without becoming fitter, set a faster
race result while threshold evidence is sparse, or improve durability while
volume falls. Keeping those signals separate makes Progress useful, auditable
and honest while still allowing a concise headline when the strongest evidence
supports one.

---

# Decision 021

**Date**
13 August 2026

## Passport Is an Evidence Identity, Not a Second Zone Model

### Status

Accepted

### Decision

Passport answers what the app currently knows about the athlete. It composes
existing evidence rather than recalculating Progress or inventing physiological
zones.

- LT1 and LT2 remain configured boundaries and always show their source.
- Recovery, Easy and Long Easy pace/HR bands describe the athlete's strongest
  conditions-adjusted historical patterns; they are not mandatory limits.
- Training profile rows show typical distance beside pace and heart rate.
  Development rows use repetition distance/count and quality volume when that
  split-level evidence exists.
- Threshold leads with observed trusted work-phase pace and keeps any cautious
  12°C flat-road equivalent visibly separate.
- VO₂ and Speed prioritise trusted repetition pace and effort because heart
  rate lags short work.
- Personal heat, hills and trail effects retain sample size and confidence and
  are described as modifiers of the generic penalty model, not percentages of
  total running pace.
- Workout-response patterns remain observational and never claim causation.
- Threshold evidence keeps three denominators visibly separate: decoded
  threshold workouts, the stricter current Progress pace-trend set and the
  smaller subset with complete before/after response windows.
- PBs and official race results remain factual and unnormalised.

The data composition lives in `core/passport_detail.py`; `ui/passport.py`
presents the typed result. The canonical athlete selector remains shared with
Home and Progress.

### Reason

Progress already answers what is changing, while Next Run answers what to do.
Passport is most useful as the stable, auditable current identity connecting
physiological boundaries, historical training behaviour, distinctive traits,
learned associations and achievements without blurring those evidence types.

---

# Decision 022

**Date**
13 August 2026

## Interactive Race Outlook Translates Capability; It Does Not Change Fitness

### Status

Accepted

### Decision

Race Predictor is a standalone primary destination. Goals owns saved outcomes;
Race Predictor answers what the athlete could run for a selected distance and
set of conditions.

- The user may select any saved goal without making it active, or explore 5K,
  5 miles, 10K, 10 miles, Half Marathon or Marathon with an optional comparison
  target.
- Every specialist evidence provider recalculates for the selected distance.
  The app does not scale the active-goal answer after the fact and never writes
  an exploratory choice back to the goals table.
- The current ideal-condition capability remains fixed while the user changes
  temperature, humidity, total ascent, wind speed/exposure and surface.
- Heat and humidity use the shared temperature/dew-point model; ascent uses the
  shared conservative climbing-density allowance; wind remains generic because
  direction is not known; firm trail uses the shared surface allowance.
- Supported personal heat, hills and trail responses scale only their relevant
  factor. Every factor retains sample/confidence provenance through the existing
  environment-profile contract.
- The result shows selected-race central time, range, pace, condition cost,
  target gap and a recalculated coaching likelihood.
- Combined summary adjustments are capped at 18% of ideal pace. This is a
  safety boundary, not a promise that every extreme course can be modelled.
- Quick-start scenarios are explicitly labelled as starting conditions. A
  separate fine-tuning section keeps every actual value visible and adjustable.

The deterministic translation lives in `core/race_outlook.py` and the controls
and responsive presentation live in `ui/race_outlook.py`.
`core/home_predictions.py` exposes an explicit-goal adapter while preserving
the active-goal Home wrapper. Goals retains goal and training-block management.

### Reason

An athlete's fitness does not change when the weather slider moves, and an
exploratory distance should not silently change the coaching goal. Separating
capability, goal choice and race-day realisation makes the model understandable
and keeps Goals free to develop a proper primary/secondary hierarchy.

---

# Decision 023

**Date**
14 August 2026

## One Active Primary Goal Drives Coaching

### Status

Accepted

### Decision

Goal priority is an explicit coaching hierarchy rather than a display label.

- Exactly one Active Primary goal may drive Home, Next Run and Training Block
  direction. `get_active_goal` never falls back to an Active Secondary goal.
- Secondary goals are tune-ups, benchmarks or supporting outcomes. They may be
  included in the active block but cannot replace its Primary direction.
- Future goals remain visible and editable but have no current coaching or
  block influence.
- Complete and Archived goals remain available as history.
- Promoting a goal preserves the previous Primary as an Active Secondary goal.
  The existing Training Block is not regenerated or reinterpreted; any mismatch
  is surfaced for deliberate review.
- Only the Primary goal can create the simple distance/date block starting
  point. A later sprint will replace that starting point with a history-led,
  customisable generator.

`core/goals.py` owns hierarchy composition and lifecycle transitions;
`ui/goals.py` owns the responsive Goal Centre and explicit management actions.
No schema change is required.

### Reason

Several saved goals are useful only if the athlete can see which one controls
today's coaching. Separating one direction from supporting and future outcomes
prevents accidental plan changes and gives the forthcoming Training Block
engine a stable, auditable contract.

---

# Decision 024

**Date**
14 August 2026

## Training History Proposes; Athlete Constraints Decide

### Status

Accepted

### Decision

The Training Block generator starts from demonstrated behaviour rather than a
generic race-plan template.

- Recent six-week days, hours and reliable mileage establish the baseline.
- The twelve-week rhythm, typical Long Easy distance and recent quality miles
  establish a cautious sustainable ceiling and session frequency.
- The athlete explicitly chooses running days, long-run day, session days,
  strength days, maximum weekly mileage and any recovery or life constraint.
- One Active Primary goal sets the end date and race-specific direction.
  Relevant Secondary races may enter the block, but replace normal quality
  load rather than silently adding intensity.
- The generated plan uses deterministic Base, Build, Specific, Taper and Race
  phases, regular cutbacks and explicit hard-day spacing warnings.
- Saving persists the evidence snapshot, athlete preferences and generated
  week/day shape. Changing the Primary goal never silently rewrites it.
- The block defines direction and weekly structure. Next Run continues to own
  the exact next workout prescription.

The pure generator lives in `core/training_block_designer.py`, persistence uses
schema v10 through `core/training_blocks.py`, and the responsive controls live
in `ui/training_blocks.py`.

### Reason

The safest useful plan is neither a frozen generic schedule nor an opaque
algorithm. Starting with what the athlete has sustainably completed and then
making real-life constraints first-class produces a plan that is explainable,
editable and much more likely to be followed.

---

# Decision 025

**Date**
14 August 2026

## Saved Plan and Real Execution Remain Separate

### Status

Accepted

### Decision

Operational Block Coaching is a read-only layer over the athlete-approved
Training Block.

- The saved week remains the factual plan.
- Real activities are matched by date and training purpose, using existing
  athlete-relative Performance Recognition before the shared classifier.
- Reliable distance contributes to mileage. An unreliable treadmill or indoor
  run may complete a day by time but never invents comparative distance.
- Complete, Different, Missed and Extra are evidence states, not automatic
  edits.
- Home and Next Run use the next incomplete saved commitment when one exists.
- If recent execution makes a hard commitment unsafe, recovery may be advised,
  but the original commitment remains visible for deliberate review.
- The operational module has no database write path. Any future adaptation
  must be explicitly accepted and auditable.

The read-only composition lives in `core/operational_block.py`. Training Blocks
owns the execution view; Home and Adaptive Coach consume the same contract.

### Reason

A plan only becomes coaching when it responds to reality. Keeping observation,
recommendation and plan mutation separate makes that response useful without
making the athlete lose control of the schedule they approved.

---

# Decision 026

**Date**
14 August 2026

## One Navigation State Uses the Approved Pathmark

### Status

Accepted

### Decision

- The persistent sidebar uses the approved Pathmark PNG rather than an inline
  approximation of the mark.
- All product and management destinations share one canonical selection state.
- Route-group spacing is presentational only; route names and page ownership
  remain stable and no overlaid or independently selectable headings are used.
- Deep links and cross-page actions set the same canonical route. One-release
  migration consumes the retired management-selection state.

### Reason

The sidebar is the product's most persistent expression. Using the real identity
and one unambiguous current route makes the growing product feel coherent without
changing any page's evidence or coaching contract.

---

# Decision 027

**Date**
14 August 2026

## Accepted Adaptations Are Overlays, Not Plan Rewrites

### Status

Accepted

### Decision

- The athlete-approved Training Block design remains the factual original.
- A Block Review shows the original commitment, proposed alternative and the
  operational evidence that caused the review.
- Accept, Defer and Reject are append-only audit actions. Every action may
  retain an athlete-entered reason and no earlier decision is deleted.
- The latest action for a deterministic review key controls the effective
  result. Only Accept activates the proposal.
- An accepted proposal is applied as a read-time overlay to one dated
  commitment. It never updates `training_block_designs.plan_json`.
- A later Defer or Reject removes the overlay while preserving the complete
  action history.
- The first supported review type protects recovery when an unexpected
  demanding run occurs within one day of the next saved hard commitment.
- Training Blocks, Home and Adaptive Coach/Next Run consume the same effective
  Operational Week rather than maintaining page-specific decisions.

Schema v11 stores the audit events in `block_review_actions`.
`core/block_review.py` owns persistence and overlay composition;
`core/operational_block.py` owns evidence and the review trigger; and
`ui/training_blocks.py` owns presentation and explicit athlete controls.

### Reason

Changing the saved JSON would make it impossible to distinguish what the
athlete originally approved from what coaching later recommended. An
append-only decision history plus a read-time overlay preserves ownership,
supports reversal and gives every consumer one transparent effective plan.
