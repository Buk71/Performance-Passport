# Performance Passport Future Features

This document captures future product ideas that should not interrupt the current sprint.

Ideas here may later move into ROADMAP.md once they become planned work.

---

# Flagship Features

## Best Ever Easy Run

Identify when an easy run was unusually strong compared with similar runs from the same athlete, after accounting for context such as heart rate, heat, elevation, terrain and fatigue.

---

## Best Ever Session

Extend the Best Ever concept beyond easy runs to include:

- Threshold sessions
- Long runs
- Interval sessions
- Hill sessions
- Race efforts

---

# Race Intelligence

## Race Planner

Recommend suitable races for an athlete based on:

- PB potential
- Elevation and course speed
- Typical weather
- Wind exposure
- Travel fatigue
- Race field depth
- Position in training cycle
- Historical performance in similar conditions

Long term, this should become personalised and learn which race conditions produce the athlete's best performances.

---

## Race Predictor

Estimate realistic race performance based on:

- Recent training
- Athlete baselines
- Fatigue
- Race distance
- Course profile
- Weather
- Historical performance

---

## Course Suitability Score

Score how suitable a race course is for the athlete based on personal strengths and weaknesses.

Examples:

- Flat fast courses
- Rolling courses
- Hot weather
- Cold weather
- Exposed windy routes
- Trail or mixed terrain

---

# Training Intelligence

## Preparation Intelligence

Identify which preparation patterns lead to the athlete's best performances.

Questions to answer:

- What preparation produced my best races?
- What 8-week blocks produced my biggest improvements?
- What mileage range works best for me?
- What taper length works best?
- How many easy days do I need before racing?

---

## Training Block Effectiveness

Analyse rolling training blocks such as:

- 4 weeks
- 6 weeks
- 8 weeks
- 12 weeks

Compare each block with the performance change that followed.

---

## Season Planner

Help plan training phases across a season:

- Base
- Build
- Race preparation
- Peak
- Recovery
- Maintenance

Long term, this could recommend how to structure training around key races.

---

# Environmental Intelligence

## Personal Weather Adjustments

Learn how different conditions affect the athlete personally.

Factors may include:

- Temperature
- Humidity
- Dew point
- Wind
- Sun exposure
- Rain
- Seasonal patterns

---

## Surface and Terrain Adjustment

Adjust performance analysis based on:

- Road
- Trail
- Gravel
- Grass
- Track
- Hills
- Technical terrain

---

## Direct Strava Import

Import activities directly from Strava using the Strava API.

Potential benefits:

- Easier ongoing activity sync
- Less manual export/import
- Access to activity metadata
- Better user experience
- Foundation for automatic dashboard updates

Important considerations:

- Strava API authentication
- API rate limits
- Privacy permissions
- Mapping Strava fields into Performance Passport activity fields
- Handling duplicates
- Preserving existing Runalyze and FIT imports

---

# Session Classification Engine

Objective

Classify activities using deterministic evidence rather than relying on activity titles.

Evidence (weighted)

★★★★★ FIT workout structure
★★★★★ Pace variability
★★★★☆ Heart-rate profile
★★★★☆ Athlete thresholds (LT1/LT2)
★★★☆☆ Maximum heart rate
★★★☆☆ Average pace
★★☆☆☆ Distance
★★☆☆☆ Duration
★★☆☆☆ Activity title

Principles

- Use multiple pieces of evidence.
- Explain every classification.
- Athlete-specific rather than generic.
- Classification confidence should be visible.
- FIT data should become the primary source of truth.

Example Output

Threshold Session

Confidence: 94%

Reasons

✓ Sustained pace near LT2
✓ Maximum HR above LT2
✓ Continuous effort
✓ Pace well above easy baseline

---

# Guiding Principle

Future features should only be promoted into active development when they answer a clear coaching question and fit the Performance Passport coaching pipeline.