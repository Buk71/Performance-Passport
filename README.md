# Performance Passport

Performance Passport is a personal running intelligence and coaching platform
built with Python, Streamlit and SQLite.

It goes beyond recording what happened by explaining what a run means compared
with the athlete's own genuinely similar historical sessions.

---

## Vision

Create the ultimate coaching dashboard that answers questions such as:

- Am I getting fitter?
- How much did the weather affect today's run?
- Was this session better than last month's?
- What pace should I run next week?
- Am I ready for a PB?

---

## Current Release

**v0.29.1 — History-Led Training Blocks**

The production app now brings together:

- Athlete Passport and Active Goal
- Latest-run interpretation and comparable-session ranking
- Three-coach race outlook
- This Week and Recommended Next Run
- Best Runs and Hall of Fame evidence
- Split-aware session classification
- Measurement-reliability safeguards, including treadmill pace exclusion
- Evidence-backed review of an individual activity
- Classification scores, continuity, splits and comparable-session ranking
- A Home navigation label that matches the production Home route
- Sidebar-aware Home composition without an over-stretched Passport
- Direct Latest Run and Best Runs links into the exact supporting Activity
  Review
- Athlete and activity selection preserved across Home evidence links
- Home selector and athlete content locked to one canonical athlete ID
- A production Progress view answering whether the athlete is improving
- Conditions-normalised aerobic efficiency with explicit sample confidence
- Twelve-week training rhythm using days, time and reliable distance
- Factual race progression that never rewrites official elapsed results
- Work-phase threshold evidence and interruption-aware durability evidence
- Shared canonical athlete selection across Home and Progress
- Safari-safe monthly aerobic efficiency chart
- Weekly training rhythm split into Easy, Long Run, Sessions and honest Other
- Threshold pace shown in min/mile as observed work pace, with a separate
  cautious 12°C flat-road equivalent range
- Race progression explicitly compares the recent six-month best with the
  previous six-month best, while keeping the all-time result separate
- A production Passport Detail answering what the app currently knows about
  each athlete
- Current LT1/LT2, threshold, aerobic-direction and durability anchors with
  explicit source and confidence
- Recovery, Easy, Long Easy, Threshold and VO₂/Speed training profiles drawn
  from the existing historical Blueprint evidence
- Typical distance and development repetition/quality volume shown beside pace
  and heart-rate or effort guidance
- Threshold support separated into decoded workouts, the strict Progress trend
  subset and complete before/after learning windows
- A standalone Race Predictor translating recalculated distance-specific
  capability into user-selected race-day conditions
- Read-only selection of any saved goal, plus independent exploration of 5K,
  5 miles, 10K, 10 miles, Half Marathon and Marathon
- Optional comparison targets for exploratory distances without changing the
  athlete's active goal
- One Active Primary goal as the sole source of current coaching direction
- Secondary tune-up and benchmark goals that can support the active block
  without replacing the Primary goal
- Future goals that remain visible but have no current coaching influence
- Explicit promotion, role changes, completion, restoration and goal editing
- Safe Primary-goal changes that preserve the previous goal as Secondary and
  flag the existing Training Block for review rather than silently rewriting it
- History-led Training Block design starting from recent days, hours, reliable
  mileage, quality load and the athlete's long-run pattern
- Custom running, session, long-run and strength days plus an explicit weekly
  mileage ceiling and recovery/life constraints
- Deterministic Base, Build, Specific, Taper and Race phases with cutbacks,
  cautious progression and week-by-week daily shapes
- Relevant Secondary races placed inside the Primary-goal block as replacement
  quality rather than hidden additional load
- Persisted evidence, athlete choices and generated weekly plan behind the
  active Training Block
- Accessible action hierarchy: ink-navy primary actions, warm-paper secondary
  actions and orange reserved for focus, warning and selected-state emphasis
- Adjustable temperature, humidity, total ascent, wind speed/exposure and
  road or firm-trail surface, plus useful scenario presets
- A factor-by-factor condition-cost audit showing personal versus generic
  support, selected-condition pace/range and revised goal likelihood
- Athlete-specific heat, hill and trail responses, learned traits and
  cautious workout-response associations
- A factual achievement ledger that keeps all-time and recent results separate

---

## Next Sprint

**Operational Block Coaching** will connect the saved weekly shape to Next Run,
completed activities and deliberate weekly adaptation without silently
rewriting athlete-approved constraints.

The next coaching question is:

> How should the saved block respond to what the athlete actually completes?

See `ROADMAP.md` for the complete scope and exclusions.

## Run

```bash
streamlit run app.py
```

---

## Technology

- Python
- Streamlit
- SQLite
- Pandas
- Plotly

---

Every feature must be validated against real athlete data before it is called
complete. Mock data is reserved for isolated unit tests.
