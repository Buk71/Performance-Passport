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

Implementation will take place during Sprint 2.3.

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