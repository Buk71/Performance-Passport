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

## Merchandise
The Pathmark, contour motif and achievement system must work on premium performance apparel as well as digital UI. Earned kit should feel like sportswear, not promotional merchandise.
