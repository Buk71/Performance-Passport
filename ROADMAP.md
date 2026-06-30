# Current Status

Current Release: **v0.3.3**

Current Sprint: **Sprint 3.4 – Athlete Baseline Foundation**

Architecture Status:
**Frozen**

Overall Progress

🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜

---

# Project Vision

Performance Passport is a coaching-focused running analysis platform.

The objective is **not** to replicate Garmin Connect, Strava or Runalyze.

Instead it should answer:

**"How good was this run, really... compared with my other similar runs?"**

Every feature should help the runner understand their training better.

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
- AI-generated coaching insights based on deterministic calculations

---

# Completed

## Sprint 1 – FIT and Runalyze Import

- ✅ GitHub repository
- ✅ Streamlit application
- ✅ SQLite database
- ✅ Database schema
- ✅ Initial import foundation

---

## Sprint 2.1 – Multi-Athlete Database and Runalyze Import

- ✅ Multi-athlete database
- ✅ Runalyze CSV importer
- ✅ Duplicate detection
- ✅ Raw JSON storage
- ✅ 3,703 activities imported

---

## Sprint 2.2 – Athlete Management

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

## Sprint 2.3 – Athlete Linking

- ✅ Added athlete_id to activities
- ✅ Linked imported activities to registered athletes
- ✅ Preserved existing imported data
- ✅ Supported multiple import sources
- ✅ Eliminated text-based athlete matching issues

---

## Sprint 3.0 – Live Dashboard Foundation

- ✅ Added working dashboard view
- ✅ Athlete selector
- ✅ Lifetime summary
- ✅ Current year summary
- ✅ Recent activities list
- ✅ Sport type display foundation

---

## Sprint 3.1 – Dashboard Presentation Improvements

- ✅ Improved dashboard presentation
- ✅ Added activity cards
- ✅ Added sport icons and readable sport names
- ✅ Improved date, duration, distance, elevation and heart-rate formatting
- ✅ Improved "Coming Next" product messaging

---

## Sprint 3.2 – Coaching Engine Foundation

- ✅ Added `core/coaching.py`
- ✅ Created reusable deterministic coaching calculation foundation
- ✅ Added distance conversion helpers
- ✅ Added pace formatting helpers
- ✅ Added min/mile and min/km pace support
- ✅ Dashboard now consumes coaching calculations instead of calculating pace directly
- ✅ Added placeholder for future aerobic efficiency calculation
- ✅ No database changes
- ✅ No architecture changes

---

## Sprint 3.3 – Training Session Classification

- ✅ Introduced `RunProfile` dataclass
- ✅ Added reusable training session classification engine
- ✅ Implemented deterministic classification rules
- ✅ Dashboard now displays run classifications
- ✅ Maintained backwards compatibility with Sprint 3.2
- ✅ No database changes
- ✅ No architecture changes

---

# Current Focus

## Sprint 3.4 – Athlete Baseline Foundation

Goal:

Teach Performance Passport what is "normal" for each athlete by building historical performance baselines.

Objectives:

- Build athlete baseline calculations.
- Compare each run against the athlete's own history.
- Prepare percentile-based coaching insights.
- Build the foundation for Best Ever Easy Run.
- Avoid database schema changes.
- Avoid architecture changes.

---

# Flagship Milestone

## Best Ever Easy Run

This is the first major flagship feature.

Goal:

Identify when an easy run was unusually good after comparing it with similar runs from the same athlete.

Future inputs may include:

- Session classification
- Athlete baseline
- Percentile ranking
- Pace
- Heart rate
- Distance
- Duration
- Elevation
- Terrain
- Heat
- Humidity
- Fatigue
- Recent training load
- Athlete history

Principle:

Build transparent deterministic calculations first.  
AI should explain the result, not invent it.

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
- Coaching highlights
- Best recent run
- Best ever easy run

---

## Activity Analysis

- Activity explorer
- Filters
- Workout types
- Route analysis
- Activity detail view
- Session classification

---

## Performance Analysis

- Heat adjustment
- Trail adjustment
- Wind adjustment
- Altitude adjustment
- Grade adjustment
- Surface adjustment

---

## Training Intelligence

- Run Classification
- Athlete Baselines
- Percentile Rankings
- Best Ever Easy Run
- Benchmark Workouts
- Durability
- Fatigue
- Freshness
- Race Readiness
- Coaching Insights
- Training Trend Explanations

---

## Coaching Engine

- Run Classification
- Athlete Baselines
- Percentile Engine
- Aerobic Efficiency
- Running Economy
- Heat Adjustment
- Terrain Adjustment
- Elevation Adjustment
- Durability Score
- Fatigue Score
- Race Readiness
- Passport Score

---

## Equipment

- Shoe management
- Shoe mileage
- Cost per mile
- Shoe recommendations
- Shoe performance comparison

---

## Performance Passport

- Endurance Score
- Speed Score
- Durability Score
- Consistency Score
- Efficiency Score
- Race Readiness Score

Combined into one overall Performance Passport Score.

---

# Development Rules

Every sprint must:

- Start from a clean Git status.
- Use the agreed architecture.
- Build one feature.
- Finish one feature.
- Keep changes small and testable.
- Explain why each change is being made.
- Test thoroughly.
- Commit only after successful testing.

Architecture changes require a dedicated refactoring sprint.

When in doubt, optimise for correctness, maintainability and coaching value rather than speed of implementation. Small, well-tested improvements are preferred over large speculative changes.