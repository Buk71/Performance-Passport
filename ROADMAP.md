---

# Current Status

Current Release: **v0.2.3**

Current Sprint: **Sprint 2.2 – Athlete Management**

Architecture Status:
**Frozen**

Overall Progress

🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜

---

# Project Vision

Performance Passport is a personal sports performance platform.

The objective is **not** to replicate Garmin Connect, Strava or Runalyze.

Instead it should provide unique analysis unavailable elsewhere.

Examples include:

- Heat-adjusted performance
- Trail and surface adjusted performance
- Best Ever Easy Run
- Benchmark workout tracking
- Durability analysis
- Fatigue & Freshness
- Race Readiness
- Shoe Performance
- Performance Passport Score

Every new feature should provide insight unavailable in existing platforms.

---

# Completed

## Sprint 1

- ✅ GitHub repository
- ✅ Streamlit application
- ✅ SQLite database
- ✅ Database schema

---

## Sprint 2.1

- ✅ Multi-athlete database
- ✅ Runalyze CSV importer
- ✅ Duplicate detection
- ✅ Raw JSON storage
- ✅ 3,703 activities imported

---

## Sprint 2.2

### Athlete Management

- ✅ Add athlete
- ✅ Edit athlete
- ✅ Delete athlete
- ✅ Duplicate prevention
- ✅ Athlete profile fields
- ✅ Athlete management page
- ✅ Architecture documented
- ✅ Roadmap documented
- ✅ Decisions log introduced

---

# Next Sprint

## Sprint 2.3 – Athlete Linking

Goal:

Replace text-based athlete matching with proper database relationships.

Objectives:

- Add athlete_id to activities
- Link imported activities to registered athletes
- Preserve existing imported data
- Support multiple import sources
- Eliminate name matching issues

---

# Future Roadmap

## Dashboard

- Athlete summary
- Total activities
- Distance
- Time
- Weekly mileage
- Monthly mileage
- Training consistency

---

## Activity Analysis

- Activity explorer
- Filters
- Workout types
- Route analysis

---

## Performance Analysis

- Heat adjustment
- Trail adjustment
- Wind adjustment
- Altitude adjustment
- Grade adjustment

---

## Training Intelligence

- Best Ever Easy Run
- Benchmark workouts
- Durability
- Fatigue
- Freshness
- Race readiness

---

## Equipment

- Shoe management
- Shoe mileage
- Cost per mile
- Shoe recommendations

---

## Performance Passport

- Endurance Score
- Speed Score
- Durability Score
- Consistency Score
- Efficiency Score

Combined into one overall Performance Passport Score.

---

# Development Rules

Every sprint must:

- Start from a clean Git status.
- Use the agreed architecture.
- Build one feature.
- Finish one feature.
- Test thoroughly.
- Commit only after testing.

Architecture changes require a dedicated refactoring sprint.