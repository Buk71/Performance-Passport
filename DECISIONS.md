# Performance Passport Decisions Log

This document records significant technical and project decisions.

It is intentionally brief.

Routine feature work belongs in ROADMAP.md.

Architecture belongs in ARCHITECTURE.md.

---

## Decision 001

**Date:** 28 June 2026

### Architecture Freeze

**Decision**

The project architecture is frozen following Sprint 2.1.

Current structure:

```text
Performance-Passport/
│
├── app.py
├── config.py
├── core/
├── ui/
├── database/
├── uploads/
├── assets/
└── tests/
```

No new folders or architectural changes will be introduced unless agreed as part of a dedicated refactoring sprint.

**Reason**

Maintain stability and avoid architecture drift.

---

## Decision 002

**Date:** 28 June 2026

### Development Workflow

**Decision**

Every sprint will:

- Start from a clean Git status.
- Have a version number.
- List all changed files.
- Provide complete replacement files whenever practical.
- Build one feature to completion.
- Be tested before committing.
- Recommend a Git commit only after testing passes.

**Reason**

Keep development predictable and easy to maintain.

---

## Decision 003

**Date:** 28 June 2026

### Athlete Management First

**Decision**

Athlete management will be completed before developing the main dashboard.

**Reason**

The dashboard depends on reliable athlete data and profiles.

---

## Proposed Decisions

These are agreed in principle but not yet implemented.

### Decision 004 (Proposed)

Activities should ultimately be linked to athletes using `athlete_id` rather than `athlete_name`.

**Reason**

This will:

- Support multiple athletes reliably.
- Eliminate issues caused by name differences.
- Simplify database queries.
- Support multiple import sources.

Status: Proposed