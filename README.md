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

**v0.23.3 — Activity Review Foundation**

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

---

## Next Sprint

**Home-to-Activity Review integration** will make Latest Run and Best Runs
open the exact supporting activity evidence.

Activity Review already answers:

> How good was this run, really—and why?

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
