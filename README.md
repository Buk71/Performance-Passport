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

**v0.25.1 — Progress Foundation**

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

---

## Next Sprint

**Passport Detail** will bring the app's learned athlete traits, confidence and
supporting achievements together in one auditable identity view.

The next coaching question is:

> What has the app learned about me—and how strong is the evidence?

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
