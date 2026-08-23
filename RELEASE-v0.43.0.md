# Performance Passport v0.43.0 — Athlete-First Coaching Evidence

This release improves the shared recognition and coaching evidence engine
without replacing the existing Streamlit/SQLite application or modifying raw
imported activities.

## What changes

- Repeated fast efforts separated by recorded slower recoveries are decoded
  in their correct chronological roles. Real 20 × 200 m and 6 × 1 km sessions
  are no longer mistaken for warm-up, cooldown, or recovery laps.
- Short separately recorded finishing strides and low-effort auto-lapped runs
  are excluded from Workout Coach prediction evidence.
- Recent substantial 10K-specific interval sessions take precedence over old,
  slow, controlled, or poorly comparable historical workout/race matches.
- Half-marathon predictions require enough sustained quality-work distance;
  short controlled sessions cannot dilute genuinely strong endurance workouts.
- Historical workout/race evidence now decays with age for every goal
  distance, not only half-marathon and longer goals.
- **Activities → Coach corrections** lets an athlete override session intent,
  exclude unreliable heart-rate data, or provide a corrected heart-rate value.
- **Athletes → Official race personal bests** lets an athlete supply the
  official 5K, 10K, or half-marathon result displayed on the Athlete Passport.
- Overrides are athlete-specific, reversible, and preserve imported source
  data. The application automatically migrates its database to schema 13.
- Legacy regression tests now isolate newly imported Jo sessions alongside
  newly imported Richard sessions, keeping historical golden baselines stable.

## Install

Make a database backup first. From the existing project root:

```bash
unzip -o ~/Downloads/Performance-Passport-v0.43.0-Athlete-First-Coaching-Evidence.zip -d .
python -m pytest -q
streamlit run app.py
```

The downloadable release deliberately excludes all athlete databases, Garmin
uploads, virtual environments, and private backups. Your existing database
remains in place.

Optional real-athlete inspection:

```bash
python scripts/validate_coaching_evidence.py
python scripts/inspect_workout_evidence.py 3
```
