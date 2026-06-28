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
Current Sprint Baseline
Sprint 2.1 completed:
GitHub repository connected
SQLite database created
Athletes table created
Activities table created
Derived metrics table created
Benchmarks table created
Multi-athlete architecture working
Runalyze CSV importer working
3,703 Runalyze activities imported
Duplicate detection working
Raw JSON stored for every activity
Sprint 2.2 Direction
Sprint 2.2 should build the first live database-powered dashboard within the existing architecture.
Expected areas of work:
ui/dashboard.py
core/database.py
possibly ui/import_page.py
possibly ui/athletes.py
Do not use Streamlit pages/ during Sprint 2.2.
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