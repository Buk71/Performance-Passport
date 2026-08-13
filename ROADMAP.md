# Performance Passport Roadmap

## Current Status

Current release: **v0.25.1 — Progress Foundation**

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
- Latest Run and Best Runs deep-link to their exact supporting Activity Review
- Athlete and historical activity selection survive Home evidence navigation
- Home's displayed selector and coaching content share one canonical athlete ID
- Progress separates aerobic fitness, training rhythm, race results, threshold
  and durability into honest evidence streams
- Supported heat, humidity/dew point, climbing, wind and trail effects are
  normalised before aerobic and threshold comparisons
- Home and Progress share the same canonical numeric athlete selector
- Aerobic efficiency uses a browser-safe monthly chart; training rhythm keeps
  total reliable mileage while showing its Easy, Long Run, Session and Other
  composition
- Threshold evidence leads with observed work-phase pace in min/mile and keeps
  the estimated 12°C flat-road equivalent as a separate limited-confidence
  range
- Race cards label both six-month comparison windows and use unambiguous
  improvement/slower wording rather than implying future capability

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

## Completed Sprint — Home Evidence Links

### Product question

**What evidence supports this Home conclusion?**

### Delivered

- Latest Run card and its visible analysis action open the exact activity.
- Featured and category Best Runs open their exact supporting activities.
- View All Runs opens Activity Review for the selected athlete.
- Linked historical activities automatically use the all-time selector window.
- Athlete and activity identity are carried through stable same-app URLs.
- Activity Review validates the linked activity against the athlete's own
  canonical history before rendering it.
- Richard and Jo deep links are covered by real-data and Streamlit handoff
  tests.
- Approved Home structure and rollback previews remain unchanged.

---

## Completed Sprint — Progress Foundation

### Coaching question

**Am I improving—and which parts of my running are changing?**

### Delivered

- A production Progress destination driven by each athlete's real history.
- Conditions-normalised aerobic efficiency over twelve months.
- Generic heat/humidity, climbing, wind and trail allowances scaled by a
  personal response only where the athlete-specific confidence is sufficient.
- Strong, moderate and limited confidence based on comparable sample support.
- Twelve-week training rhythm using active days, moving time and reliable
  distance without pretending consistency itself is fitness.
- Factual 5K, 10K and Half Marathon progress using trusted elapsed results;
  official results and PBs are never environmentally rewritten.
- Threshold evidence based on trusted work phases rather than whole-run pace.
- Durability evidence based on pace decoupling from continuous Long Easy runs,
  with interrupted runs excluded.
- Treadmill time remains useful for rhythm while unreliable treadmill pace and
  distance remain excluded from performance trends.
- Richard and Jo regression coverage plus a Streamlit production-route smoke
  test and canonical athlete-state validation.

---

## Following Priorities

1. Passport detail: learned traits, evidence confidence and achievements.
2. Interactive Race Outlook with combined Hot, Hilly, Trail and Windy inputs.
3. Login-led athlete identity and Coach Mode athlete switching.
4. Direct Strava/Garmin integration through the canonical activity model.

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
