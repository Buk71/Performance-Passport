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

## Merchandise
The Pathmark, contour motif and achievement system must work on premium performance apparel as well as digital UI. Earned kit should feel like sportswear, not promotional merchandise.
