Performance Passport v0.64.3b — Post-build Source Version Fix

The v0.64.3 diagnostic found the exact issue:
- race intelligence WAS being written;
- the athlete source version was stable between normal reads;
- but an existing builder performed a maintenance write during calculation;
- field 28 (workout_library MAX(updated_at)) advanced while the build was running;
- v0.64.3 then saved the new intelligence against the *old* pre-build version;
- therefore every subsequent lookup rejected it as stale.

This patch keeps the strict invalidation model but, after a cache miss, stores
the result against the source version observed after the build completes.

Replace:
  core/materialized_intelligence.py
  core/home_predictions.py
  core/distance_prediction_outlook.py
  core/race_coach.py

Add:
  tests/test_materialized_postbuild_version.py

Run:
  python -m pytest tests/test_materialized_intelligence.py tests/test_materialized_postbuild_version.py tests/test_shared_race_intelligence.py tests/test_significant_evidence.py tests/test_official_pb_precedence.py -q

Then run the intelligence diagnostic again:
  python tools/diagnose_v0643_intelligence_store.py --athlete 1

Old rows may still show stale versions until the first new build. Then rerun:
  python tools/benchmark_v064.py --athlete 1

Expected:
- Pass 1 can still populate/rebuild.
- Pass 2 should hit materialised race intelligence and be dramatically faster.
