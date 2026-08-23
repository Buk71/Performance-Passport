# Performance Passport v0.44.0 — Personal Threshold Estimation

This release gives athletes a useful LT1/LT2 starting point when they have not
completed formal threshold testing, while keeping verified evidence in control.

## What changed

- Added automatic personal LT1 and LT2 heart-rate estimates from each athlete's
  reliable sustained-running history.
- Added an evidence range, confidence label, sample count and latest evidence
  date so estimates do not look more precise than the data supports.
- Heart-rate exclusions and corrected activity heart rates are respected by the
  estimator.
- Added a three-way threshold comparison to the Athletes page: training
  estimate, profile/test value and the value currently used by the coaches.
- Added a verified test override for laboratory, field-test or coach-assessed
  LT1/LT2/max-HR values, with test date and notes.
- Clarified the Settings threshold controls and source labels.

## Evidence hierarchy

The coaching engine now uses threshold evidence in this order:

1. enabled verified test or coach-assessed values;
2. existing athlete profile values;
3. automatic training-history estimates when profile values are blank.

Automatic estimates are field estimates, not laboratory measurements. A test
override can be cleared at any time to return to the profile or automatic value.

## Validation

- Real-data checks cover Richard, Jo and Paul independently.
- Existing profile values remain active for all three athletes, so their current
  coach predictions are unchanged by this release.
- A synthetic new-athlete test verifies that automatic estimates become active
  when LT1/LT2 profile values are absent.
- Source compiles cleanly and the affected regression suite passes in the
  project compatibility harness.

## Install and verify

Replace the project files with this release, preserving your existing
`database/performance_passport.db`, then run:

```bash
python -m pytest -q
streamlit run app.py
```

The release archive intentionally contains no athlete database or uploaded
private data.
