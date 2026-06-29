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

Schema v1

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

Activities currently originate from Runalyze.

Future sources include:

- FIT files
- Garmin
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

## Schema v2 (Planned)

- Athlete identities
- Athlete ID relationships
- Schema version tracking

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