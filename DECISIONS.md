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