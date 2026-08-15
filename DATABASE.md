# Performance Passport Database

## Overview

The Performance Passport database is the core of the application.

The application, user interface and analysis all depend on the database.

The primary design goals are:

- Preserve all imported data.
- Never lose original source information.
- Support multiple athletes.
- Support multiple import sources.
- Build derived intelligence without altering source data.

---

# Current Schema

Current Database Version

Schema v12

## Tables

### athletes

Stores the registered athletes managed within Performance Passport.

Primary Key

```
id
```

Current fields

- first_name
- last_name
- date_of_birth
- sex
- height_cm
- weight_kg
- resting_hr
- max_hr
- lt1_hr
- lt2_hr
- notes

---

### activities

Stores imported activities.

Activities currently originate from:

- Runalyze CSV
- Garmin FIT files and Garmin export ZIPs

Future sources include:

- Garmin Activity API
- Strava
- COROS
- Polar
- GPX

Current key fields

- athlete_name
- source
- source_activity_id
- activity_hash
- activity_datetime
- raw_json

Garmin imports also retain the immutable original FIT binary under
`uploads/garmin/<athlete_id>/`. The repository ignores these private source
files. `raw_json` stores normalised session, lap, device and record-coverage
evidence while the binary remains available for future record-level analysis.

---

### derived_metrics

Stores Performance Passport calculated metrics.

Examples:

- Heat adjustment
- Trail adjustment
- Durability
- Fatigue
- Freshness
- Race readiness

No imported data is overwritten.

---

### benchmarks

Stores benchmark performances and key workouts.

---

### training_block_designs

Stores the athlete-approved generator preferences, evidence snapshot and
original `plan_json` for each saved Training Block.

### block_review_actions

Stores append-only Accept, Defer and Reject events for a deterministic review
key. Each event retains the original commitment, proposed alternative,
supporting evidence and optional athlete reason. The latest event determines
whether a read-time overlay is active; this table never rewrites the saved
Training Block design.

### athlete_nutrition_profiles

Stores one independent dietary profile per athlete, including dietary style,
servings, allergy/dislike filters, cooking-time preference, budget approach,
batch-cooking preference and optional nutrition-detail display.

### nutrition_week_selections

Stores the athlete's explicit recipe choice for each date and meal slot in a
saved Training Block week. Ingredient quantities remain in the curated code
catalogue; the database stores stable recipe IDs and serving counts so a
shopping list can be reproduced without altering the running plan.

---

# Current Relationships

```
Athlete

↓

Activities

↓

Derived Metrics

↓

Benchmarks
```

---

# Planned Schema Evolution

## Schema v2

Athlete Identity

New table

```
athlete_identities
```

Purpose

Map external identities to registered athletes.

Example

| Athlete | Source | External Name |
|----------|----------|---------------|
| Richard Burke | Runalyze | Richard |
| Richard Burke | Garmin | Richard Burke |
| Jo Burke | Runalyze | Jo |

Activities will reference:

```
athlete_id
```

while preserving

```
athlete_name
```

for audit purposes.

---

## Future Schema

Schema v3

Shoes

Schema v4

Routes

Schema v5

Environmental conditions

Schema v6

Performance Passport metrics

---

# Database Principles

1. Never lose imported source data.

2. Derived calculations must never overwrite imported values.

3. Relationships should use IDs rather than names.

4. Every schema evolution must be backwards compatible where practical.

5. Database migrations should be incremental and reversible.

---

# Migration Strategy

Each schema evolution should follow this order.

1. Add new tables and columns.

2. Migrate existing data.

3. Update the application.

4. Remove obsolete fields only after successful migration and testing.

---

# Database Version History

## Schema v1

- Athletes
- Activities
- Derived Metrics
- Benchmarks

## Schema v2

- Athlete identities
- Athlete ID relationships
- Schema version tracking

## Schema v3–v9

- Goals, decoded workouts, sport mappings and workout evidence foundations
- Physiological threshold overrides
- Training Blocks and goal/block relationships
- Activity identity and duplicate-safety improvements

## Schema v10

- Persisted history-led `training_block_designs`

## Schema v11

- Append-only `block_review_actions`
- Athlete- and block-scoped review history
- Original and proposed commitment evidence preserved as JSON

## Schema v12

- Independent `athlete_nutrition_profiles`
- Saved, athlete-scoped `nutrition_week_selections`
- Stable recipe IDs and serving counts for reproducible shopping lists

---

# Future Vision

Performance Passport is designed as a long-term sports performance database.

The database should ultimately support:

- Multiple athletes
- Multiple sports
- Multiple import sources
- Unlimited derived analysis
- Historical preservation of all imported data

The database is considered the permanent record.

The user interface is simply one way of interacting with that data.
