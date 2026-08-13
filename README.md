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

**v0.26.1 — Passport Distance Evidence**

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
- Athlete-specific heat, hill and trail responses, learned traits and
  cautious workout-response associations
- A factual achievement ledger that keeps all-time and recent results separate

---

## Next Sprint

**Interactive Race Outlook** will allow combined Hot, Hilly, Trail and Windy
conditions to be explored without rewriting the athlete's factual results.

The next coaching question is:

> How does my current capability change under a specific combination of race
> conditions?

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
