# Performance Passport Roadmap

---

## Project Status

Current Version: v0.2.1

Architecture Status:
Frozen

Current Sprint:
Sprint 2.2

Overall Progress:
🟩🟩⬜⬜⬜⬜⬜⬜⬜⬜

---

# Project Vision

Performance Passport is a personal sports performance platform.

The objective is not to replicate Garmin Connect, Strava or Runalyze.

Instead, it should generate unique insights unavailable elsewhere.

Core areas include:

- Heat-adjusted performance
- Surface-adjusted performance
- Best ever easy run
- Benchmark workout tracking
- Durability analysis
- Fatigue & freshness
- Race readiness
- Shoe performance
- Personal Performance Passport Score

---

# Completed

## Sprint 1

✅ GitHub repository created

✅ Streamlit application created

✅ SQLite database created

✅ Athletes table

✅ Activities table

✅ Derived metrics table

✅ Benchmarks table

---

## Sprint 2.1

✅ Runalyze CSV importer

✅ Duplicate detection

✅ Raw JSON storage

✅ Multi-athlete support

✅ Imported 3,703 Runalyze activities

---

# Current Sprint

## Sprint 2.2

Goal:

Build the first database-powered dashboard using the existing architecture.

Success criteria:

- Dashboard displays live statistics.
- Athlete summary works.
- Activities page works.
- Database queries cleaned up.
- No architectural changes.

---

# Next Sprint

## Sprint 2.3

Planned:

- FIT file importer
- Merge FIT activities into activities table
- Duplicate detection across FIT + Runalyze
- Activity detail view

---

# Future Backlog

## Dashboard

- Weekly mileage
- Monthly mileage
- Training load
- Longest streak
- Running consistency

---

## Performance Analysis

- Heat adjustment
- Trail adjustment
- Wind adjustment
- Altitude adjustment
- Grade adjustment

---

## Training Intelligence

- Best easy run
- Benchmark workouts
- Fitness trend
- Fatigue trend
- Freshness score
- Race readiness

---

## Equipment

- Shoe mileage
- Shoe wear prediction
- Best shoe by workout
- Cost per mile

---

## Passport Score

- Endurance
- Speed
- Durability
- Consistency
- Efficiency

Combined into a single Performance Passport Score.

---

# Development Rules

Every sprint must:

- Start from a clean Git commit.
- Build one feature.
- Finish one feature.
- Test completely.
- Commit to Git.

No architecture changes without an explicit refactoring sprint.

---

# Ideas Parking Lot

Anything that is a good idea but not currently a sprint should be placed here instead of changing the roadmap.