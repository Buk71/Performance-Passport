# Performance Passport Design System v1

**Lead mark:** Pathmark interlocking PP  
**Motto:** *Every run has something to give.*

## Visual DNA
- Ink navy `#10263D`
- Warm paper `#F7F3EC`
- Performance orange `#F05A28`
- Progress green `#3E8E72`
- Topographic/route-line motif
- Clean line-icon language; remove random emoji UI
- Large performance numbers, restrained cards, generous whitespace

## Signature Coach Home — approved v0.22

1. Athlete identity and compact Active Goal
2. Athlete Passport beside Performance Intelligence
3. Race Outlook aligned with the Passport baseline
4. This Week and Up Next
5. Best Runs / Hall of Fame evidence

The approved reference is the v11 responsive composition. Typography uses a
10px minimum, natural-height panels and an 8px page rhythm. Desktop alignment
and compact-screen Active Goal wrapping are release requirements.

The athlete selector remains temporary. Normal athlete identity will
eventually come from login; coach-mode switching will live in navigation. At
that point Active Goal can span the full Home width.

## Responsive rule
Mobile-first, desktop-expanded. No hover-only information. Week ribbon scrolls horizontally; cards stack; decisions stay above deep analysis.

At intermediate desktop content widths created by the expanded Streamlit
sidebar, Passport and Performance Intelligence share the first-row baseline;
Race Outlook spans the full second row. Every coach, condition and goal status
must remain visible without an over-stretched Passport or horizontal clipping.

## Activity Review — v0.23

Activity Review follows the Home density system and keeps the evidence order
stable:

1. Activity identity and classification confidence.
2. Distance, time, pace, heart rate and continuity.
3. Classification evidence beside athlete-relative comparison.
4. Work/recovery structure beside conditions and terrain.
5. Positive coaching meaning, followed by expandable audit detail.

Classification, measurement reliability and performance comparison must use
visually distinct treatments. Uncertain results use explicit confidence text;
excluded pace never appears as a valid performance number. The 10px type floor
from Home applies here too.

## Evidence links — v0.24

Home evidence cards remain visually identical when they become links. The
visible “View full analysis” and “View all runs” actions provide the primary
affordance, while the complete Latest Run and Best Run cards are also clickable
and keyboard accessible. Linked cards use the performance-orange focus ring;
no information or navigation may depend on hover alone.

## Progress — v0.25

Progress answers one question first: **Am I improving?** The hierarchy is:

1. Overall verdict and confidence.
2. Aerobic fitness, training rhythm, threshold and durability status cards.
3. Twelve-month aerobic and twelve-week rhythm charts.
4. Factual race progression.
5. Threshold and durability evidence rules.

Progress green is reserved for supported positive direction and confidence,
not decorative emphasis. Limited evidence remains visible rather than being
hidden or converted into a score. Race times use factual elapsed results; the
conditions-normalised treatment is visually and verbally confined to aerobic
and threshold comparisons. Charts have text summaries and tooltips, use a 10px
type floor and collapse to single-column evidence at compact widths.

Weekly rhythm preserves total reliable mileage as bar height. Stacked colour
shows Easy (green), Long Run (ink), Sessions (orange) and any genuinely Other
distance (neutral). Monthly aerobic efficiency uses browser-safe CSS bars so
the evidence remains visible in Safari as well as Chromium-based browsers.

Athlete-facing pace in Progress is displayed in min/mile. Threshold cards lead
with observed trusted work-phase pace. Any 12°C flat-road equivalent appears
as a separate range with explicit confidence language; it is never styled as a
measured or confirmed threshold.

Race Progression must label its comparison windows directly: Recent 6-month
best, Previous 6-month best and All-time best. Direction language describes
historical change (for example, “18s improvement”), never predicted headroom.

## Passport Detail — v0.26.1

Passport answers one question first: **What has the app learned about me?**
The hierarchy is:

1. Athlete identity, age grade and overall evidence confidence.
2. Current LT1, LT2, threshold, aerobic-direction and durability anchors.
3. Historical training profile by runner-friendly purpose.
4. Personal environmental responses and distinctive trait.
5. Observational workout-response learning.
6. Factual achievement ledger and expandable evidence rules.

Training profiles must label pace in min/mile and place heart rate and typical
distance beside pace, not merge them into an opaque zone score. Development
work may show repetition structure and total quality distance. Strong, moderate and limited
evidence remain visible. Current anchors use compact equal-weight cards; the
training profile uses an aligned table on desktop and readable stacked rows at
compact widths. Orange identifies development work and audit focus; green is
reserved for supported confidence and positive direction.

## Merchandise
The Pathmark, contour motif and achievement system must work on premium performance apparel as well as digital UI. Earned kit should feel like sportswear, not promotional merchandise.

## Standalone Race Predictor — v0.27.1

Race Outlook keeps a stable left-to-right story: Current Capability → Condition
Cost → Selected Race → Comparison Target. The ideal capability card must not
visually change with the controls. Selected Race uses ink; condition cost uses
orange; goal context uses the warm gold treatment.

Prediction basis appears first and distinguishes a read-only saved goal from
standard-distance exploration. Quick-start scenario buttons are introduced as
starting conditions, followed by a separately labelled fine-tuning section
that always exposes the actual numeric values. Presets never hide or lock
inputs. Below the headline comparison, equal factor cards show heat/humidity,
climbing, wind and surface cost with personalised/generic provenance. Compact
layouts stack the comparison in reading order and preserve all factor evidence
without hover.

## Goal Hierarchy — v0.28

Goals answers **What am I targeting?** before exposing forms or block actions.
The hierarchy hero states the one goal leading coaching and keeps current block
context visually separate. Three equal role summaries explain Primary,
Secondary and Future before the detailed goals.

Primary uses progress green and states that it drives Home, Next Run and block
direction. Secondary uses performance orange for tune-ups and benchmarks.
Future uses a neutral treatment and explicitly states that it has no current
coaching effect. Every detailed card keeps target, distance and date together,
followed by a distinct coaching-influence explanation. Role changes require
visible actions; changing Primary never silently restyles or regenerates a
Training Block. Compact layouts preserve the same reading order without hover.

## History-Led Training Blocks — v0.29

Training Blocks answers **How should I prepare?** using this hierarchy:

1. Primary goal and the athlete's demonstrated starting point.
2. Explicit, editable real-life constraints.
3. Generated block direction and safety explanations.
4. Week-by-week progression, recovery, taper and event placement.
5. One selected week's daily shape.

Recent rhythm, reliable mileage, typical long run and supported session count
appear as evidence, not prescriptions. User controls remain clearly separate
from the generated result. Weekly cards use total mileage as the dominant
number, green for planned progression and orange only for events or cautions.
Secondary races replace quality load rather than visually or physiologically
stacking on top of it. Exact workout prescription remains owned by Next Run.

## Action hierarchy — v0.29.1

Native app buttons use purpose rather than page identity:

- Primary actions use ink navy with white text. These are reserved for the one
  consequential action in a section, such as saving an active Training Block,
  saving a goal or deliberately changing the Primary goal.
- Secondary actions use a white/warm-paper surface, ink text and a visible
  neutral border. Scenario presets, lifecycle alternatives and supporting
  actions belong here.
- Performance orange is an accent for focus rings, warnings, events, selected
  states and progress marks; it is not the default button background.
- Keyboard focus keeps an orange ring, while hover never carries information
  unavailable to touch users.

## Operational Block Coaching — v0.30

The current week leads with execution rather than another plan preview:

1. Week state and phase.
2. Reliable distance, running-day, quality and long-run commitments.
3. Seven planned days with explicit Complete, Different, Missed, Extra, Today
   or Planned status.
4. Evidence-led suggestions beside the next safe useful run.
5. A permanent statement that the saved plan has not been silently changed.

Green marks genuine matched completion. Orange marks a difference requiring
review, not failure. Ink outlines Today and anchors the next-run decision.
Operational cards remain readable at intermediate sidebar widths and collapse
to two then one/two-column groups without hiding evidence.

Generated week cards are complete keyboard-accessible links, not hover-only
controls. The selected week uses an ink border and opens its seven-day shape
immediately below the timeline. Unsaved proposals show an explicit activation
notice where the operational panel will appear after saving.

Week selection must preserve page and athlete context. A selected week may
rerender the Streamlit app, but it must return to Training Blocks with the same
canonical athlete rather than falling back to Home.

## Pathmark Navigation — v0.31

The persistent sidebar uses the approved Pathmark artwork directly; it must not
be redrawn as an approximate inline icon. Navigation is one ordered route whose
journey stages are separated by clear, quiet spacing.

Quiet waypoint dots make the route scannable. The active destination uses ink
text on warm paper with an orange leading edge, while hover and keyboard focus
remain distinct. Visual groups do not create independent selection states and
the interface never exposes a `None` destination.

## Deliberate Block Review — v0.32

Block Review appears directly beneath the Operational Week that produced it.
The comparison is always explicit: warm-paper Approved Commitment on the left,
the green-supported Proposed Commitment on the right and an orange direction
marker between them. Compact layouts stack the same reading order.

Pending and Deferred use restrained orange because athlete attention is still
required. Accepted uses progress green; Rejected uses neutral ink/grey. Colour
never replaces the written decision. The evidence, original session, proposed
session, date, latest decision and athlete reason remain visible without hover.

Accept is the one primary action. Defer and Reject remain secondary actions.
Every review states that the saved Training Block remains preserved and that
the accepted result is a one-day overlay, not a hidden plan rewrite.

## Training Blocks readability — v0.32.1

Desktop Training Blocks cards use their available space rather than compressing
supporting evidence into caption-sized type. Explanatory copy is at least 12px,
with central rationale and week-card emphasis at 13–14px. Week dates, session
counts and action labels remain visually secondary but must be readable without
zooming. The same floor applies to daily-shape, Operational Week and Block
Review supporting text. Existing container breakpoints preserve the hierarchy
on narrower screens.

## Weekly Fuel Planner — v0.33

Fuel Planner visually follows the approved block rather than competing with it.
The next-week summary uses a progress-green top rule and a permanent written
lock explaining that meals cannot change training. Four equal demand cards
show Rest/Recovery, Easy, Quality and Long run/Race composition before any food
choices appear.

Each day leads with the saved session purpose and before/during/after guidance,
then uses native accessible select controls for breakfast, lunch, dinner and
recovery snack. Dietary style, allergens, preparation time and optional
nutrition estimates remain visible in text; colour never communicates food
suitability by itself. Supporting copy keeps the same 12–14px readability floor
introduced for Training Blocks.

The shopping list is an outcome of deliberately saved choices, not a generic
recipe catalogue. It uses familiar grocery categories, native checkboxes and a
download action. Individual athlete lists are the default; household combining
must be explicitly selected.

Omnivore and pescatarian main-meal choices must show deliberate range rather
than allowing the larger plant-based catalogue to dominate through simple
rotation. The first lunch/dinner option represents the selected mixed-diet
style; the second remains a complete plant-based alternative. Breakfast and
recovery snacks stay naturally mixed without token meat additions.
