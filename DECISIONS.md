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
