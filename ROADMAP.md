# Performance Passport Roadmap

## Current Status

Current release: **v0.23.3 — Activity Review Foundation**

Architecture status: **Frozen**

Approved production baseline:

- Coach Home v11 responsive composition
- Jo and Richard athlete imagery
- Shared split-aware session classification
- Treadmill pace-reliability exclusion
- Real-data validation for both athletes
- Production Activity Review using the shared intelligence engines
- Home and Activities production navigation labels
- Intermediate-width Home composition for an expanded sidebar

---

## Product Vision

Performance Passport is a coaching-focused running analysis platform. It does
not aim to reproduce Garmin Connect, Strava or Runalyze. Its defining question
is:

> How good was this run, really, compared with my other similar runs after
> accounting for its purpose and conditions?

Deterministic calculations create the conclusion. AI may explain those
calculations, but must not invent them.

---

## Completed Foundations

### Data and athlete identity

- Multi-athlete SQLite database
- Runalyze import, duplicate detection and raw source preservation
- FIT foundation
- Athlete management and `athlete_id` linking
- Richard and Jo validated independently against real historical data

### Coaching intelligence

- Athlete baselines and comparable-session rankings
- Split-aware session classification with confidence safeguards
- Best Runs and Hall of Fame recognition
- Race predictions and coach consensus
- Athlete Passport and learned traits
- Training Blocks, Goals and adaptive weekly coaching
- Journal, Learning and Recommended Next Run foundations
- Treadmill pace-reliability policy across comparative consumers

### Product design

- Pathmark PP identity and Design System v1
- Approved responsive Coach Home
- Active Goal, Performance Intelligence, Race Outlook, This Week, Up Next and
  Best Runs hierarchy
- Desktop Passport/Race Outlook alignment
- Compact-screen Active Goal treatment
- Activity Review hierarchy with a 10px type floor and responsive evidence cards

---

## Completed Sprint — Activity Review

### Coaching question

**How good was this run, really—and why?**

### Delivered

The Activities placeholder is now an evidence-backed review destination.

### Complete slice

- Select and open a real activity.
- Show the shared session classification and confidence.
- Explain the evidence supporting that classification.
- Show moving, elapsed and interruption context.
- Present split/work-recovery structure where source data allows.
- Compare the run only with genuinely comparable sessions.
- Show rank, percentile and the reason it performed well or poorly.
- Make pace-reliability exclusions visible, including treadmill handling.
- Provide a concise coaching interpretation grounded in the calculations.
- Validate the complete screen against representative Richard and Jo sessions.

### Preserved exclusions

- No manual activity editing.
- No route-map rebuild.
- No AI-generated unsupported scoring.
- No new top-level architecture.
- No combined-condition Race Outlook yet.

---

## Following Priorities

1. Link Home Latest Run and Best Runs into Activity Review and complete visual
   approval at desktop and compact widths.
2. Progress: longitudinal fitness, efficiency and durability trends.
3. Passport detail: learned traits, evidence confidence and achievements.
4. Interactive Race Outlook with combined Hot, Hilly, Trail and Windy inputs.
5. Login-led athlete identity and Coach Mode athlete switching.
6. Direct Strava/Garmin integration through the canonical activity model.

---

## Development Rules

Every sprint must:

- Start from a clean Git status in Richard's real repository.
- Use the agreed architecture.
- Build one feature to completion.
- Keep changes small and testable.
- Validate calculations against the real current database.
- Preserve Richard and Jo as independent athletes.
- Explain any measurement exclusions and confidence limits.
- Update tests and documentation.
- Commit only after successful testing.
