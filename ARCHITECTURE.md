# Performance Passport Architecture

## Current Version

Architecture baseline: Sprint 2.1  
Status: Frozen until explicitly changed

## Purpose

Performance Passport is a long-term sports performance analysis app.

It is designed to import and store running and training data, then build unique analysis on top of it, including:

- Heat-adjusted performance
- Trail and surface adjustments
- Best ever easy run
- Benchmark workout tracking
- Durability
- Fatigue and freshness
- Race readiness
- Shoe performance
- Personal Performance Passport Score

## Project Principles

Performance Passport is designed as a long-term engineering project.

Primary goals:

- Build stable software before adding features.
- Prefer simple architecture over clever architecture.
- Avoid unnecessary refactoring.
- Every sprint should leave the project in a working state.
- Git is the source of truth.
- The SQLite database is considered production data and should never be recreated unless explicitly intended.

## Architecture Change Policy

Architecture changes are intentionally rare.

Before changing the project structure, the following questions must be answered:

1. What problem exists today?
2. What measurable improvement will the new architecture provide?
3. Why should the change happen now rather than later?
4. What is the migration plan?
5. Can the project be rolled back using Git if required?

If these questions cannot be answered clearly, the architecture should remain unchanged.

## Long-Term Vision

Performance Passport is not intended to compete directly with Garmin Connect, Strava or Runalyze.

Instead, it should become the user's personal performance laboratory.

Future capabilities include:

- Heat-adjusted running performance
- Trail and surface adjusted performance
- Best ever easy run detection
- Durability analysis
- Fatigue modelling
- Race readiness scoring
- Shoe lifecycle analysis
- Benchmark workout tracking
- Performance trend forecasting
- Personal Performance Passport Score

Every new feature should provide insight that existing running platforms do not.

## Agreed Project Structure

```text
Performance-Passport/
│
├── app.py
├── config.py
│
├── core/
│   └── database.py
│
├── ui/
│   ├── dashboard.py
│   ├── athletes.py
│   ├── import_page.py
│   └── sidebar.py
│
├── database/
│   └── performance_passport.db
│
├── uploads/
├── assets/
└── tests/
Folder Responsibilities
app.py
Main Streamlit entry point.
Responsibilities:
Set Streamlit page configuration
Initialise the database
Render the sidebar
Route the user to the selected UI page
config.py
Central configuration.
Responsibilities:
App name
File paths
Database path
Upload path
Shared constants
core/
Application logic and database operations.
Current file:
core/database.py
Responsibilities:
Create database tables
Manage SQLite connections
Insert athletes
Insert activities
Detect duplicate activities
Import Runalyze CSV data
Store raw JSON
Support future FIT imports
ui/
Streamlit user interface pages.
Current files:
ui/dashboard.py
ui/athletes.py
ui/import_page.py
ui/sidebar.py
Responsibilities:
Display the dashboard
Manage athletes
Import Runalyze CSV files
Render navigation
Keep Streamlit presentation separate from core database logic
database/
SQLite database storage.
Current file:
database/performance_passport.db
Responsibilities:
Store athletes
Store activities
Store derived metrics
Store benchmarks
Store raw imported data
uploads/
Temporary or persistent uploaded files.
Responsibilities:
Store uploaded Runalyze CSV files
Store future uploaded FIT files
assets/
Static project assets.
Responsibilities:
Images
Icons
Future branding assets
tests/
Testing area.
Responsibilities:
Future test files
Import tests
Database tests
Calculation tests
Architecture Rules
The architecture is frozen after Sprint 2.1.
Do not create or use these folders unless explicitly agreed in a future refactor:
pages/
utils/
services/
New folders should only be introduced after answering:
Why is the current architecture insufficient?
What measurable benefit does the new architecture provide?
Why is the migration worth doing now?
If those criteria are not met, continue using the existing structure.
Development Workflow
Every sprint must follow this process:
Start from a clean committed Git version.
Inspect the current files before proposing changes.
Use the existing architecture unless a refactor is explicitly agreed.
Provide a version number, for example v0.2.2.
List all changed files.
Provide complete replacement files whenever practical.
Build one feature to completion before moving on.
Explain architectural decisions.
Test the feature before committing.
Recommend a Git commit message only after testing passes.
Current Release Baseline

Version 0.29.1 preserves the approved Home, Activity Review, Progress,
Passport Detail and Race Predictor and adds the Goal Hierarchy layer:

- `ui/home.py` owns the production Home route.
- The approved v11 responsive composition remains available as the visual
  reference and rollback history.
- `app.py` routes Home, Activities and Race Predictor to their production page
  functions.
- Home calculations continue to come from the existing `core/` coaching,
  prediction, recognition and summary modules.
- Split-aware session classification is shared across product consumers.
- Treadmill session history is retained while unreliable treadmill distance
  and pace are excluded from comparative performance intelligence.
- Real-data regression tests cover Richard and Jo independently.
- `core/activity_review.py` joins, but does not replace, the shared
  classification, reliability, split and recognition engines.
- `ui/activities.py` contains presentation and selection only; it does not
  recalculate classifications or rankings.
- `ui/activity_navigation.py` owns the small, stable query-parameter contract
  used by Home evidence links. It contains no coaching calculation.
- `ui/sidebar.py` honours a validated Activity Review navigation request before
  its existing radio widget is created.
- `ui/activities.py` consumes the request once, selects the correct athlete and
  activity, and then returns control to the normal selectors.
- Production Home uses the shared canonical athlete ID as its selector widget
  state, preventing a page-specific display value diverging from its content.
- The production Home wrapper reuses the approved generated intelligence
  sections in an intermediate-only grid: Passport and Performance Intelligence
  share the first-row baseline, while Race Outlook spans the second row. The
  approved full-width and compact v11 layouts remain intact, and no calculation
  is duplicated.
- `core/progress.py` owns longitudinal evidence selection, comparison windows,
  confidence and verdicts. It consumes the shared reliability, environment,
  recognition and race-anchor engines rather than duplicating them.
- `core/performance_recognition.py` exposes its conservative environment pace
  normalisation as an auditable result. Existing recognition ranks continue to
  use the unchanged generic wrapper; Progress may provide a sufficiently
  supported personal environment profile.
- `ui/progress.py` owns Progress presentation and responsive charts only. It
  receives a complete `ProgressSummary` and does not calculate coaching
  conclusions.
- Progress monthly and stacked weekly charts use ordinary HTML/CSS inside the
  Streamlit HTML component for consistent Safari rendering. Weekly purpose
  mileage comes from the existing shared recognition categories.
- Race evidence always exposes factual elapsed results. Environmental context
  may support interpretation but never mutates a PB or source result.
- Threshold comparisons use supported work-phase pace. Durability comparisons
  use decoupling only from continuous Long Easy evidence.
- Threshold stores observed phase pace separately from its conditions-normalised
  comparison value. The UI may show a deliberately broad 12°C flat-road
  equivalent range, but must not relabel that estimate as confirmed threshold.
- `ui/athlete_selection.py` exposes the canonical numeric selector used by both
  Home and Progress, preventing page-specific athlete state from diverging.
- `core/passport_detail.py` composes athlete identity, Progress anchors,
  effective thresholds, Training Blueprint, personal environment profile and
  observational Learning Engine output. It does not create a parallel zone or
  prediction model.
- `ui/passport.py` owns Passport presentation and receives one typed
  `PassportDetail`. Pace is displayed in min/mile; factual results are never
  conditions-normalised.
- Passport labels configured LT1/LT2 boundaries with their source. Historical
  pace/HR ranges are training patterns rather than laboratory zones or
  mandatory prescriptions.
- `core/home_predictions.py` exposes its existing run-profile loader and
  environment story adapter so Passport can reuse those calculations without
  invoking the slower active-goal prediction pipeline.
- `core/home_predictions.py` exposes `build_goal_predictions` for explicit,
  read-only goal or distance exploration and keeps `build_home_predictions` as
  the active-goal Home contract.
- `core/race_outlook.py` accepts the existing typed `HomePredictions` capability
  plus explicit race conditions. It translates capability into selected-race
  time without rebuilding or mutating the underlying fitness estimate.
- Race Outlook reuses the shared temperature/dew-point, climbing-density, wind
  and trail allowances. Supported personal heat, hill and trail response scales
  the relevant factor only; wind remains generic because direction is absent.
- `ui/race_outlook.py` owns the standalone Race Predictor route, explicit saved
  goal or standard-distance selection, interactive controls and presentation.
  Its schema-versioned cache keys include the selected prediction basis and it
  contains no coaching formula.
- `ui/goals.py` retains goal and training-block management and the canonical
  numeric athlete selector. It does not own race-condition exploration.
- `core/goals.py` owns Primary, Secondary, Future and Past composition plus
  deliberate role/lifecycle transitions. It never recalculates fitness or
  silently changes Training Block design.
- `core/database.py::get_active_goal` returns only an Active Primary goal. An
  Active Secondary goal can never become the implicit coaching goal.
- Promoting a goal demotes the previous Active Primary to Active Secondary.
  Existing Training Block links remain factual and are surfaced for review.
- `ui/goals.py` presents one direction and multiple outcomes, allows explicit
  role/lifecycle actions and offers block creation only for the Primary goal.
- `core/training_block_designer.py` owns deterministic history composition,
  preference validation, safe phase/volume progression, Secondary-event
  placement and serialisable weekly plans. It does not prescribe the next
  detailed workout.
- `core/training_blocks.py` persists the athlete-approved preferences, evidence
  snapshot and generated plan against the existing Training Block identity.
- Database schema v10 adds `training_block_designs`; existing blocks and goals
  are preserved and upgraded in place.
- `ui/training_blocks.py` owns controls and responsive presentation. It may
  deliberately save or update a block, but never hides a Primary-goal mismatch
  or silently rewrites the previous active block.

Next Sprint Direction

Connect the saved weekly shape to Next Run and completed activity evidence,
with auditable adaptations that preserve athlete-approved constraints.
Notes
The project should prioritise stability over restructuring.
Architecture changes are allowed later, but only as deliberate refactoring sprints, not as accidental changes during feature development.

## Design Philosophy

Performance Passport should favour:

- Simplicity over cleverness.
- Readability over brevity.
- Stability over rapid change.
- Incremental improvements over large rewrites.

The project should be understandable by its owner after months away from the codebase.

When there is a choice between a simpler design and a more technically advanced design, the simpler design should normally be preferred unless there is a measurable benefit.


---

## Training Blocks – v0.14

Training Blocks are the organising context for Version 1.0.

Hierarchy:

Season → Training Block → Goals → Sessions → Recognition

A block stores:

- purpose;
- dates;
- status;
- block type;
- primary focus;
- current phase;
- goals belonging to the block.

The Block Engine lives in `core/training_blocks.py`.

Training Blocks do not replace goals. A goal is an outcome; a Training Block is
the period of coaching designed to pursue one or more outcomes.

Future Decision Engine, Recommended Next Run and Dynamic Plan releases should
consume the active Training Block as context before giving advice.
