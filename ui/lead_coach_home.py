"""Premium Lead Coach Home built entirely from existing athlete services.

The page is a presentation layer only. It does not introduce a prediction,
session-recognition or training-plan formula; every athlete-specific value is
composed from the established Performance Passport services.
"""

from __future__ import annotations

import datetime
import html
from pathlib import Path
import re

import streamlit as st

from core.athlete_passport import build_athlete_passport
from core.distance_prediction_outlook import build_distance_prediction_outlook
from core.home_latest_run import build_home_latest_run
from core.home_prediction_matrix import build_home_prediction_matrix
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.activity_navigation import activity_review_url
from ui.athlete_card import image_to_data_uri
from ui.athlete_selection import render_athlete_id_selector
from ui.coaching_navigation import coaching_team_url
from ui.training_coach_navigation import training_coach_url
from ui.nutrition_coach_navigation import nutrition_coach_url
from ui.recovery_coach_navigation import recovery_coach_url


ROOT = Path(__file__).resolve().parent.parent
HOME_CACHE_SCHEMA = 1
HOME_DISTANCE_CACHE_SCHEMA = 1

DAILY_COACHING_TIPS = (
    (
        "Fuel before the session",
        "If you need a meal before running, leave roughly two to three hours. "
        "A small familiar snack can sit closer to the start when needed.",
        "Nutrition Coach",
    ),
    (
        "Easy means repeatable",
        "The best easy pace is the one that leaves enough energy for the next "
        "important session—not the fastest pace that still feels comfortable.",
        "Training Coach",
    ),
    (
        "Recovery starts at the finish",
        "After a demanding run, begin with fluid and a normal meal containing "
        "carbohydrate and protein rather than searching for a perfect product.",
        "Nutrition Coach",
    ),
    (
        "Judge the purpose, not one number",
        "Heat, hills and wind can change pace. A successful session is one that "
        "delivers its intended effort in the conditions you actually faced.",
        "Lead Coach",
    ),
    (
        "Keep strides distinct",
        "Short relaxed strides sharpen coordination. They should finish an easy "
        "run feeling smooth, not turn it into a hidden interval workout.",
        "Training Coach",
    ),
    (
        "Protect the night before",
        "A consistent sleep routine usually contributes more to tomorrow's run "
        "than one last-minute training or nutrition intervention.",
        "Recovery Coach",
    ),
    (
        "Start controlled",
        "In a repetition session, the first rep should establish the rhythm. "
        "Finishing with control gives the coach better evidence than fading.",
        "Workout Coach",
    ),
    (
        "Train the athlete you are today",
        "Use the plan as direction, then respect unusual fatigue, illness or pain. "
        "One adjusted day is cheaper than forcing a compromised week.",
        "Lead Coach",
    ),
    (
        "Long runs reward patience",
        "A controlled first half protects form and fuel for the later miles, where "
        "the most useful endurance evidence is often created.",
        "Endurance Coach",
    ),
    (
        "Practise race-day choices",
        "Use selected long or race-specific sessions to rehearse familiar food, "
        "drink and kit. Race day is a poor time for a first experiment.",
        "Race Coach",
    ),
    (
        "Consistency beats compensation",
        "A missed run does not create a debt. Resume the useful sequence instead "
        "of squeezing two demanding sessions together.",
        "Lead Coach",
    ),
    (
        "Use effort on hills",
        "Let pace slow on sustained climbs and keep the effort appropriate. The "
        "terrain is already adding load; the watch need not add another target.",
        "Environment Coach",
    ),
    (
        "Easy days absorb hard days",
        "Adaptation happens between demanding sessions. Recovery running and rest "
        "are part of the programme, not gaps in it.",
        "Recovery Coach",
    ),
    (
        "Look for a trend",
        "One unusually good or poor run is evidence, not a verdict. Repeated "
        "comparable performances tell the more reliable story.",
        "Lead Coach",
    ),
)


@st.cache_data(show_spinner=False, ttl=120)
def _cached_lead_coach_data(athlete_id: int, schema: int):
    del schema
    return (
        build_athlete_passport(athlete_id),
        build_home_summary(athlete_id),
        build_home_predictions(athlete_id),
        build_home_latest_run(athlete_id),
    )


@st.cache_data(show_spinner=False, ttl=900)
def _cached_distance_outlook(athlete_id: int, predictions, schema: int):
    del schema
    return build_distance_prediction_outlook(
        athlete_id,
        active_predictions=predictions,
    )


def _safe(value) -> str:
    return html.escape(str(value or ""))


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _pace_per_mile(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "—"
    seconds = float(seconds_per_km) * 1.609344
    minutes, remainder = divmod(int(round(seconds)), 60)
    return f"{minutes}:{remainder:02d}/mi"


def _distance(distance_km: float | None) -> str:
    if distance_km is None:
        return "—"
    return f"{distance_km / 1.609344:.1f} mi"


def _photo_path(first_name: str, last_name: str) -> Path | None:
    slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        f"{first_name} {last_name}".strip().lower(),
    ).strip("_")
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = ROOT / "assets" / "athletes" / f"{slug}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _tip_for_date(today: datetime.date) -> tuple[str, str, str]:
    return DAILY_COACHING_TIPS[today.toordinal() % len(DAILY_COACHING_TIPS)]


def _today_day(summary):
    return next((day for day in summary.week_days if day.is_today), None)


def _lead_briefing(summary) -> tuple[str, str]:
    today = _today_day(summary)
    if today is not None and today.session_family == "completed":
        return (
            "Today’s work is banked. Recover for what comes next.",
            f"{today.detail} is recorded. The next useful direction is "
            f"{summary.next_label.lower()} {summary.next_timing.lower()}.",
        )
    if today is not None and today.session_family == "rest":
        return (
            "Protect today’s recovery.",
            f"The plan leaves space today before {summary.next_label.lower()} "
            f"{summary.next_timing.lower()}.",
        )
    if today is not None and today.session_family in {
        "threshold", "vo2", "speed", "race_pace"
    }:
        return (
            "Give today’s key session one clear purpose.",
            f"{today.title} is the priority. Execute {today.detail.lower()} with "
            "enough control for the final repetition to remain useful.",
        )
    return (
        "Keep today controlled and make the next key session count.",
        f"The current direction is {summary.next_label.lower()} "
        f"{summary.next_timing.lower()}. {summary.next_detail}",
    )


def _passport_pbs(passport) -> str:
    rows = []
    for pb in passport.personal_bests:
        rows.append(
            f"""
            <div class="lc-pb">
                <span>{_safe(pb.label)}</span>
                <strong>{_clock(pb.all_time_seconds)}</strong>
                <small>{_clock(pb.last_12_months_seconds)} recent</small>
            </div>
            """
        )
    return "".join(rows)


def _passport_photo(passport) -> str:
    photo_path = _photo_path(passport.first_name, passport.last_name)
    if photo_path is None:
        return f'<div class="lc-photo-fallback">{_safe(passport.initials)}</div>'
    return (
        f'<img class="lc-athlete-photo" src="{image_to_data_uri(photo_path)}" '
        f'alt="{_safe(passport.full_name)}">'
    )


def _icon_markup(name: str) -> str:
    """Return Streamlit-safe CSS line icons.

    Streamlit's HTML sanitiser can remove inline SVG paths while leaving their
    coloured containers behind. These icons use only ordinary elements and
    CSS borders, so Safari and deployed Streamlit render them consistently.
    """
    supported = {
        "run", "calendar", "pulse", "training", "race", "recovery",
        "nutrition",
    }
    icon_name = name if name in supported else "pulse"
    return (
        f'<span class="lc-icon lc-icon-{_safe(icon_name)}" '
        'aria-hidden="true"><i></i><i></i><i></i></span>'
    )


def _focus_cards(athlete_id: int, summary, latest) -> str:
    today = _today_day(summary)
    if today is None:
        today_title = summary.next_label
        today_detail = summary.next_detail
        today_meta = summary.next_timing
    elif today.session_family == "completed":
        today_title = "Completed"
        today_detail = today.detail
        today_meta = today.title
    else:
        today_title = today.title
        today_detail = today.detail
        today_meta = today.target or "Today"

    latest_link = html.escape(
        activity_review_url(athlete_id, latest.activity_id),
        quote=True,
    )
    latest_title = latest.title if latest.available else "Evidence building"
    latest_detail = (
        latest.headline if latest.available
        else "Your latest reliable run will appear here."
    )
    latest_meta = (
        f"{_distance(latest.distance_km)} · {_pace_per_mile(latest.actual_pace_s_per_km)}"
        if latest.available else "Activity Review"
    )
    latest_wrapper = "a" if latest.available else "article"
    latest_href = (
        f' href="{latest_link}" target="_self"' if latest.available else ""
    )
    training_link = html.escape(training_coach_url(athlete_id), quote=True)

    return f"""
        <div class="lc-focus-grid">
            <a class="lc-focus-card lc-focus-today lc-focus-link" href="{training_link}" target="_self">
                <div class="lc-card-kicker">{_icon_markup("run")}<span>Today’s run</span></div>
                <div class="lc-card-title">{_safe(today_title)}</div>
                <p>{_safe(today_detail)}</p>
                <div class="lc-card-meta">{_safe(today_meta)} <span>Open Training Coach →</span></div>
            </a>
            <a class="lc-focus-card lc-focus-link" href="{training_link}" target="_self">
                <div class="lc-card-kicker">{_icon_markup("calendar")}<span>Next key session</span></div>
                <div class="lc-card-title">{_safe(summary.next_label)}</div>
                <p>{_safe(summary.next_detail)}</p>
                <div class="lc-card-meta">{_safe(summary.next_timing)} · {_safe(summary.next_source)} <span>Full session →</span></div>
            </a>
            <{latest_wrapper} class="lc-focus-card lc-focus-link"{latest_href}>
                <div class="lc-card-kicker">{_icon_markup("pulse")}<span>Last run</span></div>
                <div class="lc-card-title">{_safe(latest_title)}</div>
                <p>{_safe(latest_detail)}</p>
                <div class="lc-card-meta">{_safe(latest_meta)} <span>Review →</span></div>
            </{latest_wrapper}>
        </div>
    """


def _coach_cards(athlete_id: int, summary, predictions) -> str:
    team_url = html.escape(coaching_team_url(athlete_id), quote=True)
    lead_time = _clock(predictions.central_seconds)
    prediction_copy = (
        predictions.consensus_headline
        if predictions.available
        else "The coaching team is waiting for enough comparable evidence."
    )
    today = _today_day(summary)
    recovery_copy = (
        "The completed work is recognised; protect the space before the next demand."
        if today is not None and today.session_family == "completed"
        else "Use the planned easy and rest days to absorb the demanding work."
    )
    cards = (
        (
            "training", "Training Coach", summary.week_theme,
            f"Next: {summary.next_label} · {summary.next_timing}", "training"
        ),
        (
            "race", "Race Coach", prediction_copy,
            f"{predictions.distance_label} outlook {lead_time}", "race"
        ),
        (
            "recovery", "Recovery Coach", recovery_copy,
            "Training balance, not a readiness score", "aerobic"
        ),
        (
            "nutrition", "Nutrition Coach",
            "Turn the training week into practical fuel, recovery meals and a shopping list.",
            "Open your personalised weekly fuel plan", "nutrition"
        ),
    )
    markup = []
    for icon_name, title, copy, meta, coach_key in cards:
        if coach_key == "training":
            href = html.escape(training_coach_url(athlete_id), quote=True)
        elif coach_key == "nutrition":
            href = html.escape(nutrition_coach_url(athlete_id), quote=True)
        elif coach_key == "aerobic":
            href = html.escape(recovery_coach_url(athlete_id), quote=True)
        else:
            href = (
                html.escape(coaching_team_url(athlete_id, coach_key), quote=True)
                if coach_key else team_url
            )
        markup.append(
            f"""
            <a class="lc-coach-card lc-coach-{_safe(icon_name)}" href="{href}" target="_self">
                <div class="lc-coach-head">
                    <span class="lc-coach-mark">{_icon_markup(icon_name)}</span>
                    <div><strong>{_safe(title)}</strong><small>Specialist perspective</small></div>
                    <span class="lc-arrow">↗</span>
                </div>
                <p>{_safe(copy)}</p>
                <div class="lc-coach-meta">{_safe(meta)}</div>
            </a>
            """
        )
    return "".join(markup)


def _week_strip(summary) -> str:
    days = []
    for day in summary.week_days:
        classes = ["lc-week-day", f"lc-day-{day.session_family}"]
        if day.is_today:
            classes.append("lc-day-today")
        status = "Complete" if day.session_family == "completed" else day.title
        days.append(
            f"""
            <article class="{' '.join(classes)}">
                <div class="lc-day-head"><span>{_safe(day.day_name[:3])}</span><i></i></div>
                <strong>{_safe(status)}</strong>
                <p>{_safe(day.detail)}</p>
                <small>{_safe(day.target or '')}</small>
            </article>
            """
        )
    return "".join(days)


def _coach_opinions(athlete_id: int, predictions) -> str:
    if not predictions.coach_positions:
        return '<div class="lc-empty">Specialist opinions are still building.</div>'
    cards = []
    for coach in predictions.coach_positions:
        link = html.escape(
            coaching_team_url(athlete_id, coach.key),
            quote=True,
        )
        lead = '<span class="lc-lead-tag">Lead</span>' if coach.is_lead else ""
        cards.append(
            f"""
            <a class="lc-opinion lc-opinion-{_safe(coach.position)}" href="{link}" target="_self">
                <div class="lc-opinion-top"><span>{_safe(coach.title)}</span>{lead}</div>
                <div class="lc-opinion-time">{_clock(coach.predicted_seconds)}</div>
                <div class="lc-opinion-bottom">
                    <span>{_safe(coach.position.title())} view</span>
                    <strong>{coach.confidence:.0%} confidence</strong>
                </div>
            </a>
            """
        )
    return "".join(cards)


def _prediction_matrix_table(
    predictions,
    passport,
    distance_outlook=None,
) -> str:
    personal_bests = {
        pb.key: pb.all_time_seconds
        for pb in passport.personal_bests
        if pb.all_time_seconds is not None
    }
    matrix = build_home_prediction_matrix(
        predictions,
        personal_bests=personal_bests,
        distance_outlook=distance_outlook,
    )
    if not matrix.available:
        return f'<div class="lc-empty">{_safe(matrix.explanation)}</div>'

    condition_detail = {
        "ideal": "Cool · flat",
        "typical": "Mild · light wind",
        "warm": "Warm conditions",
        "hilly": "Rolling course",
        "windy": "Exposed",
        "trail": "Representative trail",
    }
    headings = "".join(
        f'<th scope="col" class="lc-matrix-{_safe(cell.key)}">'
        f'<strong>{_safe(cell.label)}</strong>'
        f'<small>{_safe(condition_detail.get(cell.key, ""))}</small></th>'
        for cell in matrix.rows[0].cells
    )
    rows = []
    for row in matrix.rows:
        active = '<span class="lc-active-distance">Active</span>' if row.is_active_distance else ""
        readiness = (
            f" · {_safe(row.readiness_label)}"
            if row.readiness_label else ""
        )
        cells = "".join(
            f'<td class="lc-matrix-{_safe(cell.key)}"><strong>{_clock(cell.seconds)}</strong></td>'
            for cell in row.cells
        )
        rows.append(
            f"""
            <tr class="{'lc-active-row' if row.is_active_distance else ''}">
                <th scope="row"><strong>{_safe(row.label)}</strong>{active}<small>{row.distance_km:g} km · {row.confidence:.0%} confidence{readiness}</small></th>
                {cells}
            </tr>
            """
        )

    return f"""
        <div class="lc-matrix-wrap">
            <table class="lc-matrix">
                <thead><tr><th scope="col"><strong>Distance</strong><small></small></th>{headings}</tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        <div class="lc-matrix-note"><strong>Ballpark capability view.</strong> {_safe(matrix.explanation)}</div>
    """


def build_lead_coach_home_html(
    athlete_id: int,
    passport,
    summary,
    predictions,
    latest,
    distance_outlook=None,
    *,
    today: datetime.date | None = None,
) -> str:
    """Return the complete premium Home markup for one real athlete."""
    today = today or datetime.date.today()
    headline, briefing = _lead_briefing(summary)
    tip_title, tip_copy, tip_coach = _tip_for_date(today)
    range_text = (
        f"{_clock(predictions.low_seconds)}–{_clock(predictions.high_seconds)}"
        if predictions.available else "Building"
    )
    confidence = (
        f"{predictions.confidence:.0%} confidence"
        if predictions.available else "Evidence building"
    )
    aerobic = (
        f"{passport.aerobic_trend_percent:+.1f}%"
        if passport.aerobic_trend_percent is not None else "—"
    )
    age_grade = (
        f"{passport.age_grade_all_time:.1f}%"
        if passport.age_grade_all_time is not None else "—"
    )
    team_url = html.escape(coaching_team_url(athlete_id), quote=True)
    training_url = html.escape(training_coach_url(athlete_id), quote=True)

    return f"""
    <main class="lc-home">
        <section class="lc-welcome">
            <div>
                <div class="lc-eyebrow lc-dark"><span></span>Your Lead Coach</div>
                <h1>Welcome back, {_safe(passport.first_name)}.</h1>
            </div>
            <div class="lc-status"><i></i> Coaching direction is active</div>
        </section>

        <section class="lc-passport">
            <div class="lc-passport-identity">
                <div class="lc-photo-shell">{_passport_photo(passport)}</div>
                <div class="lc-live-profile"><i></i> Live profile</div>
                <div class="lc-identity-copy">
                    <div class="lc-identity-label">Athlete passport</div>
                    <h2>{_safe(passport.full_name)}</h2>
                    <div class="lc-category">{_safe(passport.category)}</div>
                </div>
            </div>

            <div class="lc-capability">
                <div class="lc-capability-top">
                    <div class="lc-current-potential">
                        <div class="lc-potential-label">Current {_safe(predictions.distance_label)} potential</div>
                        <div class="lc-potential-central">{_clock(predictions.central_seconds)}</div>
                        <div class="lc-potential-range">{_safe(range_text)} · {_safe(confidence)}</div>
                    </div>
                    <div class="lc-active-goal">
                        <div class="lc-potential-label">Active goal</div>
                        <strong>{_safe(summary.goal_name)}</strong>
                        <small>{_safe(summary.goal_context)}</small>
                    </div>
                </div>
                <div class="lc-capability-rule"><span></span></div>
                <div class="lc-stat-grid">
                    <div class="lc-age-grade">
                        <span>Age grade</span>
                        <strong>{_safe(age_grade)}</strong>
                        <small>Best performance</small>
                    </div>
                    {_passport_pbs(passport)}
                </div>
                <div class="lc-capability-footer">
                    <span>Aerobic direction <strong>{_safe(aerobic)}</strong></span>
                    <span>Evidence <strong>{_safe(confidence)}</strong></span>
                    <span>{_safe(summary.block_name)}</span>
                </div>
            </div>

            <div class="lc-coach-briefing">
                <div class="lc-eyebrow"><span></span>Today’s coaching briefing</div>
                <h2>{_safe(headline)}</h2>
                <p>{_safe(briefing)}</p>
                <a href="{training_url}" target="_self" class="lc-primary-action">See today’s plan <b>→</b></a>
                <div class="lc-coach-footer"><strong>Five coaches</strong><span>One clear direction.</span></div>
                <small class="lc-block-context">{_safe(summary.block_context)}</small>
            </div>
        </section>

        <section class="lc-focus-heading">
            <div>
                <div class="lc-eyebrow lc-dark"><span></span>What matters today</div>
                <h2>Your day, at a glance.</h2>
            </div>
            <a href="{team_url}" target="_self">Meet your coaching team →</a>
        </section>

        {_focus_cards(athlete_id, summary, latest)}

        <section class="lc-section">
            <div class="lc-section-heading">
                <div><div class="lc-eyebrow lc-dark"><span></span>One team · one direction</div><h2>Meet the coaches behind your day.</h2></div>
                <a href="{team_url}" target="_self">See the evidence behind every opinion →</a>
            </div>
            <div class="lc-coach-grid">{_coach_cards(athlete_id, summary, predictions)}</div>
            <div class="lc-team-synthesis">
                <span>//</span>
                <div><p>{_safe(briefing)}</p><strong>Lead Coach</strong></div>
            </div>
        </section>

        <section class="lc-section lc-week-section">
            <div class="lc-section-heading">
                <div><div class="lc-eyebrow lc-dark"><span></span>Your Training Coach</div><h2>This week has a purpose.</h2></div>
                <div class="lc-source">{_safe(summary.block_name)}</div>
            </div>
            <div class="lc-week-summary"><strong>{_safe(summary.week_theme)}</strong><span>{_safe(summary.block_context)}</span></div>
            <div class="lc-week-grid">{_week_strip(summary)}</div>
        </section>

        <section class="lc-section lc-outlook-section">
            <div class="lc-race-heading">
                <div><div class="lc-eyebrow lc-dark"><span></span>Your Race Coach</div><h2>Your potential in real conditions.</h2></div>
                <div class="lc-race-anchor">
                    <span>Lead Coach · {_safe(predictions.distance_label)}</span>
                    <strong>{_clock(predictions.central_seconds)}</strong>
                    <small>{predictions.confidence:.0%} confidence</small>
                </div>
            </div>
            <div class="lc-opinion-grid">{_coach_opinions(athlete_id, predictions)}</div>
            {_prediction_matrix_table(predictions, passport, distance_outlook)}
        </section>

        <section class="lc-daily">
            <div class="lc-daily-number">{today.strftime('%d')}</div>
            <div>
                <div class="lc-eyebrow"><span></span>Today’s coaching thought · {_safe(tip_coach)}</div>
                <h2>{_safe(tip_title)}</h2>
                <p>{_safe(tip_copy)}</p>
            </div>
            <div class="lc-daily-date">{today.strftime('%A')}<strong>{today.strftime('%B %Y')}</strong></div>
        </section>

        <style>
            .lc-home {{ --navy:#08253e; --navy2:#0d3653; --ink:#10273d; --muted:#607181; --orange:#f15a2a; --green:#279675; --cream:#f7f4ee; --display:"Avenir Next",Avenir,Inter,ui-sans-serif,system-ui,sans-serif; color:var(--ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
            .lc-home * {{ box-sizing:border-box; }}
            .lc-home a {{ color:inherit; text-decoration:none; }}
            .lc-home h1,.lc-home h2,.lc-card-title,.lc-opinion-time,.lc-matrix td strong {{ font-family:var(--display); }}
            .lc-welcome {{ display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin:3px 0 20px; }}
            .lc-welcome h1 {{ margin:8px 0 0; color:var(--navy); font-size:42px; line-height:1; letter-spacing:-.045em; }}
            .lc-status {{ display:flex; align-items:center; gap:9px; margin-bottom:2px; padding:10px 15px; border-radius:999px; background:#eaf6f0; color:#257c61; font-size:12px; font-weight:850; }}
            .lc-status i {{ width:8px; height:8px; border-radius:50%; background:var(--green); box-shadow:0 0 0 4px rgba(39,150,117,.12); }}
            .lc-passport {{ position:relative; display:grid; grid-template-columns:minmax(230px,.72fr) minmax(470px,1.35fr) minmax(360px,1fr); min-height:360px; overflow:hidden; border:1px solid #dcd6cd; border-radius:28px; background:#fff; box-shadow:0 24px 55px rgba(10,33,53,.14); }}
            .lc-passport-identity {{ position:relative; min-height:360px; overflow:hidden; background:var(--navy); color:#fff; }}
            .lc-photo-shell {{ position:absolute; inset:0; overflow:hidden; background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(0,0,0,.18)); }}
            .lc-athlete-photo {{ width:100%; height:100%; object-fit:cover; object-position:center 25%; filter:saturate(.92) contrast(1.04); }}
            .lc-photo-shell:after {{ content:""; position:absolute; inset:0; background:linear-gradient(180deg,rgba(4,24,40,.08) 20%,rgba(4,24,40,.34) 54%,rgba(4,24,40,.96) 100%); }}
            .lc-photo-fallback {{ display:grid; place-items:center; height:100%; font-size:54px; font-weight:900; color:rgba(255,255,255,.5); }}
            .lc-live-profile {{ position:absolute; z-index:2; top:20px; right:18px; display:flex; align-items:center; gap:7px; padding:7px 10px; border:1px solid rgba(255,255,255,.22); border-radius:999px; background:rgba(5,31,50,.68); color:#fff; font-size:9px; font-weight:850; letter-spacing:.11em; text-transform:uppercase; backdrop-filter:blur(8px); }}
            .lc-live-profile i {{ width:7px; height:7px; border-radius:50%; background:#73dfb6; box-shadow:0 0 0 4px rgba(115,223,182,.14); }}
            .lc-identity-copy {{ position:absolute; z-index:2; right:25px; bottom:25px; left:25px; }}
            .lc-identity-label {{ color:#ff8b68; font-size:10px; font-weight:900; letter-spacing:.16em; text-transform:uppercase; }}
            .lc-identity-copy h2 {{ margin:8px 0 0; color:#fff!important; font-size:37px; line-height:.98; letter-spacing:-.045em; }}
            .lc-eyebrow {{ display:flex; align-items:center; gap:10px; color:#8ee2c4; font-size:12px; font-weight:850; letter-spacing:.17em; text-transform:uppercase; }}
            .lc-eyebrow span {{ width:28px; height:3px; border-radius:999px; background:var(--orange); }}
            .lc-eyebrow.lc-dark {{ color:#6a7987; }}
            .lc-category {{ margin-top:10px; color:#d2dce3; font-size:12px; font-weight:750; letter-spacing:.13em; text-transform:uppercase; }}
            .lc-capability {{ display:flex; min-width:0; flex-direction:column; padding:29px 30px 25px; background:#fff; }}
            .lc-capability-top {{ display:grid; grid-template-columns:minmax(0,1.08fr) minmax(180px,.92fr); gap:25px; align-items:start; }}
            .lc-current-potential {{ padding-right:24px; border-right:1px solid #e4dfd7; }}
            .lc-potential-label {{ color:#738390; font-size:10px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; }}
            .lc-potential-central {{ margin-top:8px; color:var(--navy); font-size:47px; line-height:1; font-weight:900; letter-spacing:-.05em; }}
            .lc-potential-range {{ margin-top:8px; color:#7a8996; font-size:11px; font-weight:700; }}
            .lc-active-goal strong,.lc-active-goal small {{ display:block; }}
            .lc-active-goal strong {{ margin-top:10px; color:var(--navy); font-size:18px; line-height:1.18; }}
            .lc-active-goal small {{ margin-top:6px; color:#7b8995; font-size:10px; line-height:1.35; }}
            .lc-capability-rule {{ height:5px; margin:22px 0 0; overflow:hidden; border-radius:999px; background:#e8e5de; }}
            .lc-capability-rule span {{ display:block; width:100%; height:100%; border-radius:inherit; background:linear-gradient(90deg,#309d7b,#54b98e); }}
            .lc-stat-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); margin-top:18px; border-top:1px solid #e4dfd7; border-bottom:1px solid #e4dfd7; }}
            .lc-stat-grid>div {{ min-width:0; padding:15px 12px 14px; border-right:1px solid #e4dfd7; }}
            .lc-stat-grid>div:first-child {{ padding-left:0; }}
            .lc-stat-grid>div:last-child {{ padding-right:0; border-right:0; }}
            .lc-stat-grid span,.lc-stat-grid small {{ display:block; color:#83909a; font-size:8px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
            .lc-stat-grid strong {{ display:block; margin-top:6px; color:var(--navy); font-size:19px; line-height:1; }}
            .lc-stat-grid small {{ margin-top:7px; overflow:hidden; font-size:7px; letter-spacing:0; text-transform:none; text-overflow:ellipsis; white-space:nowrap; }}
            .lc-capability-footer {{ display:flex; flex-wrap:wrap; gap:14px 20px; margin-top:auto; padding-top:17px; color:#7a8894; font-size:9px; font-weight:750; }}
            .lc-capability-footer strong {{ color:var(--green); }}
            .lc-coach-briefing {{ position:relative; display:flex; min-width:0; flex-direction:column; overflow:hidden; padding:31px 31px 25px; background:radial-gradient(circle at 95% 5%,rgba(64,158,149,.22),transparent 34%),linear-gradient(135deg,#09243c,#0b334b); color:#fff; }}
            .lc-coach-briefing:after {{ content:""; position:absolute; right:-145px; top:-190px; width:390px; height:390px; border:42px solid rgba(255,255,255,.035); border-radius:50%; }}
            .lc-coach-briefing>* {{ position:relative; z-index:1; }}
            .lc-coach-briefing h2,.lc-section h2,.lc-daily h2 {{ margin:19px 0 0; font-size:28px; line-height:1.08; letter-spacing:-.035em; }}
            .lc-coach-briefing h2,.lc-daily h2 {{ color:#fff!important; }}
            .lc-coach-briefing p {{ margin:14px 0 0; color:#d2dee5!important; font-size:13px; line-height:1.55; }}
            .lc-primary-action {{ display:flex; align-items:center; align-self:flex-start; gap:20px; margin-top:20px; padding:12px 13px 12px 17px; border-radius:11px; background:var(--orange); color:#fff!important; font-size:12px; font-weight:850; white-space:nowrap; }}
            .lc-primary-action b {{ display:grid; place-items:center; width:28px; height:28px; border-radius:9px; background:var(--orange); font-size:16px; }}
            .lc-primary-action b {{ background:rgba(255,255,255,.15); }}
            .lc-coach-footer {{ display:flex; gap:10px; margin-top:auto; padding-top:19px; border-top:1px solid rgba(255,255,255,.13); color:#fff; font-size:10px; }}
            .lc-coach-footer strong {{ color:#78dab8; text-transform:uppercase; letter-spacing:.08em; }}
            .lc-block-context {{ display:block; margin-top:7px; color:#91a5b4; font-size:8px; line-height:1.25; }}
            .lc-focus-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-top:28px; }}
            .lc-focus-heading h2 {{ margin:7px 0 0; color:var(--navy); font-size:28px; font-weight:550; line-height:1.08; letter-spacing:-.025em; }}
            .lc-focus-heading>a {{ color:var(--green); font-size:12px; font-weight:850; }}
            .lc-focus-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:13px; margin-top:13px; }}
            .lc-focus-card {{ display:flex; min-height:190px; flex-direction:column; padding:23px 24px; border:1px solid #dfd9d0; border-radius:19px; background:#fff; box-shadow:0 12px 30px rgba(36,44,50,.055); }}
            .lc-focus-today {{ background:linear-gradient(145deg,#fff7f0,#fff); border-color:#f1c4ae; }}
            .lc-card-kicker {{ display:flex; align-items:center; gap:9px; color:#738592; font-size:10px; font-weight:850; letter-spacing:.13em; text-transform:uppercase; }}
            .lc-card-kicker .lc-icon {{ width:19px; height:19px; color:#6e8796; }}
            .lc-card-title {{ margin-top:20px; font-size:25px; font-weight:550; letter-spacing:-.025em; }}
            .lc-focus-card p {{ margin:9px 0 14px; color:#7a8995; font-size:13px; line-height:1.48; }}
            .lc-card-meta {{ margin-top:auto; color:#607181; font-size:11px; font-weight:750; }}
            .lc-card-meta span {{ float:right; color:var(--green); }}
            .lc-focus-link {{ transition:transform .16s ease,box-shadow .16s ease; }}
            .lc-focus-link:hover,.lc-coach-card:hover,.lc-opinion:hover {{ transform:translateY(-2px); box-shadow:0 15px 32px rgba(11,38,60,.11); }}
            .lc-section {{ margin-top:24px; padding:30px; border:1px solid #ded8cf; border-radius:23px; background:#fff; box-shadow:0 14px 36px rgba(36,44,50,.055); }}
            .lc-section-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:24px; }}
            .lc-section-heading>a {{ color:var(--green); font-size:12px; font-weight:850; }}
            .lc-section-heading h2 {{ font-weight:550; letter-spacing:-.025em; }}
            .lc-source {{ max-width:360px; color:#748390; font-size:11px; font-weight:700; text-align:right; }}
            .lc-coach-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:11px; margin-top:20px; }}
            .lc-coach-card {{ display:flex; min-height:168px; flex-direction:column; padding:17px; border:1px solid #e5e0d9; border-radius:15px; background:#fff; transition:transform .16s ease,box-shadow .16s ease; }}
            .lc-coach-training {{ border-color:#cce3d8; background:#f5faf7; }}
            .lc-coach-head {{ display:flex; align-items:center; gap:11px; }}
            .lc-coach-mark {{ display:grid; place-items:center; width:42px; height:42px; border-radius:12px; background:#eef7f2; color:var(--green); }}
            .lc-coach-race .lc-coach-mark {{ background:#fff0eb; color:var(--orange); }}
            .lc-coach-recovery .lc-coach-mark {{ background:#eef4f9; color:#557b9b; }}
            .lc-coach-nutrition .lc-coach-mark {{ background:#faf4e9; color:#9a7848; }}
            .lc-coach-mark .lc-icon {{ width:25px; height:25px; }}
            .lc-icon {{ position:relative; display:inline-block; flex:0 0 auto; color:currentColor; }}
            .lc-icon i {{ position:absolute; display:block; background:currentColor; border-radius:99px; }}
            .lc-icon-run i,.lc-icon-training i {{ bottom:18%; width:10%; }}
            .lc-icon-run i:nth-child(1),.lc-icon-training i:nth-child(1) {{ left:18%; height:42%; }}
            .lc-icon-run i:nth-child(2),.lc-icon-training i:nth-child(2) {{ left:45%; height:70%; }}
            .lc-icon-run i:nth-child(3),.lc-icon-training i:nth-child(3) {{ right:18%; height:52%; }}
            .lc-icon-calendar {{ border:2px solid currentColor; border-radius:4px; }}
            .lc-icon-calendar:before {{ content:""; position:absolute; right:-2px; top:27%; left:-2px; border-top:2px solid currentColor; }}
            .lc-icon-calendar i {{ top:-15%; width:2px; height:25%; }}
            .lc-icon-calendar i:nth-child(1) {{ left:25%; }} .lc-icon-calendar i:nth-child(2) {{ right:25%; }} .lc-icon-calendar i:nth-child(3) {{ display:none; }}
            .lc-icon-pulse i,.lc-icon-recovery i {{ top:49%; height:2px; transform-origin:left center; }}
            .lc-icon-pulse i:nth-child(1),.lc-icon-recovery i:nth-child(1) {{ left:8%; width:30%; }}
            .lc-icon-pulse i:nth-child(2),.lc-icon-recovery i:nth-child(2) {{ left:34%; width:32%; transform:rotate(-58deg); }}
            .lc-icon-pulse i:nth-child(3),.lc-icon-recovery i:nth-child(3) {{ left:57%; width:35%; transform:rotate(45deg); }}
            .lc-icon-race i {{ display:none; }}
            .lc-icon-race:before {{ content:""; position:absolute; left:24%; top:10%; bottom:8%; border-left:2px solid currentColor; }}
            .lc-icon-race:after {{ content:""; position:absolute; left:29%; top:12%; width:45%; height:36%; border:2px solid currentColor; border-left:0; border-radius:0 3px 3px 0; }}
            .lc-icon-nutrition {{ border:2px solid currentColor; border-radius:50%; }}
            .lc-icon-nutrition i:nth-child(1) {{ top:46%; left:22%; width:56%; height:2px; }}
            .lc-icon-nutrition i:nth-child(2) {{ top:22%; left:46%; width:2px; height:56%; }}
            .lc-icon-nutrition i:nth-child(3) {{ display:none; }}
            .lc-coach-head small,.lc-coach-head strong {{ display:block; }}
            .lc-coach-head small {{ margin-top:3px; color:#8a969f; font-size:8px; font-weight:700; letter-spacing:.02em; }}
            .lc-coach-head strong {{ font-size:14px; }}
            .lc-arrow {{ margin-left:auto; color:var(--green); font-weight:900; }}
            .lc-coach-card p {{ display:-webkit-box; overflow:hidden; margin:14px 0 9px; color:#71818e; font-size:11px; line-height:1.4; -webkit-box-orient:vertical; -webkit-line-clamp:2; }}
            .lc-coach-meta {{ margin-top:auto; color:#3f6f5e; font-size:10px; font-weight:800; }}
            .lc-team-synthesis {{ display:flex; gap:16px; margin-top:20px; padding:19px 8px 3px; border-top:1px solid #e7e2db; }}
            .lc-team-synthesis>span {{ color:var(--green); font-family:var(--display); font-size:24px; font-weight:850; letter-spacing:-.12em; }}
            .lc-team-synthesis p {{ margin:0; color:#6f808e; font-size:13px; line-height:1.5; }}
            .lc-team-synthesis strong {{ display:block; margin-top:8px; color:var(--green); font-size:10px; }}
            .lc-week-section {{ background:#fbfaf7; }}
            .lc-week-summary {{ display:flex; align-items:center; justify-content:space-between; gap:20px; margin-top:20px; padding:11px 14px; border-radius:11px; background:#f2f6f2; color:#48665b; font-size:10px; }}
            .lc-week-summary span {{ color:#7b8984; text-align:right; }}
            .lc-week-grid {{ display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:7px; margin-top:19px; }}
            .lc-week-day {{ min-width:0; min-height:145px; padding:14px 13px; border:1px solid #e2ddd5; border-radius:13px; background:#fff; }}
            .lc-day-head {{ display:flex; justify-content:space-between; color:#798895; font-size:10px; font-weight:850; letter-spacing:.13em; text-transform:uppercase; }}
            .lc-day-head i {{ width:7px; height:7px; border-radius:50%; background:#d9dce0; }}
            .lc-week-day strong {{ display:block; margin-top:15px; color:var(--navy); font-size:14px; line-height:1.15; }}
            .lc-week-day p {{ display:-webkit-box; overflow:hidden; margin:8px 0; color:#7b8994; font-size:10px; line-height:1.35; -webkit-box-orient:vertical; -webkit-line-clamp:3; }}
            .lc-week-day small {{ color:#738593; font-size:9px; font-weight:750; }}
            .lc-day-today {{ border:2px solid var(--orange); background:#fff7f1; box-shadow:0 7px 17px rgba(241,90,42,.12); }}
            .lc-day-today .lc-day-head i {{ background:var(--orange); }}
            .lc-day-completed {{ background:#eef8f3; border-color:#b7dfcf; }}
            .lc-day-completed .lc-day-head i {{ background:var(--green); }}
            .lc-outlook-section {{ background:linear-gradient(180deg,#fff,#faf8f4); }}
            .lc-race-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:28px; }}
            .lc-race-heading h2 {{ margin-top:15px; font-weight:550; letter-spacing:-.03em; }}
            .lc-race-anchor {{ display:grid; min-width:235px; grid-template-columns:1fr auto; align-items:end; gap:2px 13px; padding:3px 0 3px 25px; border-left:1px solid #e3ded6; }}
            .lc-race-anchor span {{ grid-column:1/-1; color:#71818d; font-size:11px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }}
            .lc-race-anchor strong {{ color:var(--green); font-family:var(--display); font-size:27px; line-height:1; letter-spacing:-.035em; }}
            .lc-race-anchor small {{ padding-bottom:2px; color:#71818d; font-size:11px; font-weight:650; }}
            .lc-opinion-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0; margin-top:22px; overflow:hidden; border:1px solid #e5e0d9; border-radius:15px; background:#f7f5f0; }}
            .lc-opinion {{ min-width:0; padding:17px 20px; border:0; border-right:1px solid #e3ded7; border-radius:0; background:transparent; transition:background .16s ease; }}
            .lc-opinion:last-child {{ border-right:0; }}
            .lc-opinion:hover {{ transform:none; background:#fff; box-shadow:none; }}
            .lc-opinion-top {{ display:flex; align-items:center; justify-content:space-between; color:#5f7180; font-size:12px; font-weight:700; letter-spacing:.055em; text-transform:uppercase; }}
            .lc-lead-tag {{ padding:4px 7px; border-radius:999px; background:var(--orange); color:#fff; font-size:9px; }}
            .lc-opinion-time {{ margin-top:8px; color:var(--navy); font-size:24px; font-weight:600!important; letter-spacing:-.025em; }}
            .lc-opinion-bottom {{ display:flex; justify-content:space-between; gap:12px; margin-top:7px; color:#657683; font-size:12px; }}
            .lc-opinion-bottom strong {{ color:#244058; font-weight:650; }}
            .lc-matrix-wrap {{ overflow-x:auto; margin-top:20px; border:1px solid #ded8cf; border-radius:16px; background:#fff; }}
            .lc-matrix {{ width:100%; min-width:830px; border-collapse:collapse; }}
            .lc-matrix th,.lc-matrix td {{ padding:16px 15px; border-right:1px solid #e5e0d8; border-bottom:1px solid #e5e0d8; text-align:left; }}
            .lc-matrix tr:last-child th,.lc-matrix tr:last-child td {{ border-bottom:0; }}
            .lc-matrix th:last-child,.lc-matrix td:last-child {{ border-right:0; }}
            .lc-matrix thead th {{ background:#f7f5f0; color:#687987; white-space:nowrap; }}
            .lc-matrix thead th strong {{ display:block; color:var(--navy); font-family:var(--display); font-size:15px; font-weight:600!important; letter-spacing:0; text-transform:none; }}
            .lc-matrix thead th small {{ display:block; margin-top:4px; color:#6f808c; font-size:11.5px; font-weight:550; letter-spacing:0; text-transform:none; }}
            .lc-matrix thead th:first-child strong {{ color:#5f7180; font-family:inherit; font-size:11px; font-weight:750!important; letter-spacing:.1em; text-transform:uppercase; }}
            .lc-matrix thead th:first-child small {{ display:none; }}
            .lc-matrix tbody th {{ position:relative; min-width:132px; background:#faf8f4; }}
            .lc-matrix tbody th strong,.lc-matrix tbody th small {{ display:block; }}
            .lc-matrix tbody th strong {{ color:var(--navy); font-family:var(--display); font-size:18px; font-weight:600!important; }}
            .lc-matrix tbody th small {{ max-width:170px; margin-top:4px; color:#607482; font-size:12px; line-height:1.3; }}
            .lc-matrix td strong {{ color:var(--navy); font-size:17px; font-weight:550!important; letter-spacing:-.015em; white-space:nowrap; }}
            .lc-matrix-ideal {{ background:#fdfaf4!important; }}
            .lc-matrix-typical {{ background:#eef8f3!important; }}
            .lc-matrix-trail {{ background:#f7f8f4!important; }}
            .lc-active-row th {{ box-shadow:inset 4px 0 0 var(--orange); }}
            .lc-active-distance {{ position:absolute; top:11px; right:9px; padding:4px 7px; border-radius:999px; background:var(--orange); color:#fff; font-size:9px; font-weight:850; letter-spacing:.06em; text-transform:uppercase; }}
            .lc-matrix-note {{ margin-top:12px; color:#526b7b; font-size:13px; line-height:1.5; }}
            .lc-matrix-note strong {{ color:#314b60; }}
            .lc-daily {{ display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:21px; margin:20px 0 8px; padding:26px 29px; overflow:hidden; border-radius:22px; background:radial-gradient(circle at 90% 10%,rgba(47,162,132,.23),transparent 30%),linear-gradient(120deg,#08243d,#0c3852); color:#fff; box-shadow:0 18px 40px rgba(8,36,61,.15); }}
            .lc-daily-number {{ display:grid; place-items:center; width:70px; height:70px; border:1px solid rgba(255,255,255,.2); border-radius:20px; background:rgba(255,255,255,.08); font-size:29px; font-weight:900; }}
            .lc-daily p {{ margin:7px 0 0; max-width:800px; color:#d6e1e7!important; font-size:14px; line-height:1.45; }}
            .lc-daily-date {{ color:#a9bbc8; font-size:11px; font-weight:750; text-align:right; }}
            .lc-daily-date strong {{ display:block; margin-top:3px; color:#fff; font-size:14px; }}
            .lc-empty {{ padding:20px; color:#687987; }}
            .lc-home a:focus-visible {{ outline:3px solid rgba(241,90,42,.65); outline-offset:3px; }}
            @media (max-width:1180px) {{
                .lc-passport {{ grid-template-columns:220px minmax(0,1fr); }}
                .lc-coach-briefing {{ grid-column:1/-1; min-height:250px; }}
                .lc-coach-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
                .lc-week-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
            }}
            @media (max-width:760px) {{
                .lc-welcome {{ align-items:flex-start; flex-direction:column; margin-bottom:15px; }} .lc-welcome h1 {{ font-size:34px; }}
                .lc-passport {{ display:block; }} .lc-passport-identity {{ min-height:285px; }}
                .lc-capability {{ padding:24px 21px; }} .lc-capability-top {{ grid-template-columns:1fr; gap:18px; }} .lc-current-potential {{ padding:0 0 18px; border-right:0; border-bottom:1px solid #e4dfd7; }}
                .lc-potential-central {{ font-size:40px; }} .lc-stat-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .lc-stat-grid>div:nth-child(2) {{ border-right:0; }} .lc-stat-grid>div:nth-child(-n+2) {{ border-bottom:1px solid #e4dfd7; }}
                .lc-coach-briefing {{ min-height:330px; padding:26px 22px; }} .lc-primary-action {{ justify-content:space-between; }}
                .lc-focus-heading {{ align-items:flex-start; flex-direction:column; }}
                .lc-focus-grid {{ grid-template-columns:1fr; }} .lc-coach-grid {{ grid-template-columns:1fr; }}
                .lc-section {{ padding:21px; }} .lc-section-heading {{ align-items:flex-start; flex-direction:column; }} .lc-source {{ text-align:left; }}
                .lc-team-synthesis {{ padding-right:0; padding-left:0; }}
                .lc-week-summary {{ align-items:flex-start; flex-direction:column; }} .lc-week-summary span {{ text-align:left; }}
                .lc-week-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
                .lc-race-heading {{ align-items:flex-start; flex-direction:column; }} .lc-race-anchor {{ width:100%; padding:12px 0 0; border-top:1px solid #e3ded6; border-left:0; }}
                .lc-opinion-grid {{ grid-template-columns:1fr; }} .lc-opinion {{ border-right:0; border-bottom:1px solid #e3ded7; }} .lc-opinion:last-child {{ border-bottom:0; }}
                .lc-outlook-table {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
                .lc-daily {{ grid-template-columns:auto 1fr; padding:22px; }} .lc-daily-date {{ display:none; }}
            }}
        </style>
    </main>
    """


def show_lead_coach_home_page() -> None:
    """Render the approved Lead Coach concept with canonical athlete data."""
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] {
                max-width:1480px;
                padding-top:4rem;
                padding-bottom:3rem;
            }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] {
                gap:10px;
            }
            [data-testid="stHeader"] { background:transparent; }
            [data-testid="stSelectbox"] { max-width:410px; }
            [data-testid="stSelectbox"] > div > div {
                min-height:48px;
                border:1px solid #d9d3ca;
                border-radius:14px;
                background:#fff;
                box-shadow:0 8px 20px rgba(30,42,52,.055);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    athlete_id = render_athlete_id_selector(
        label="Athlete",
        label_visibility="collapsed",
    )
    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    with st.spinner("Your coaching team is reviewing the latest evidence…"):
        passport, summary, predictions, latest = _cached_lead_coach_data(
            athlete_id,
            HOME_CACHE_SCHEMA,
        )
        distance_outlook = _cached_distance_outlook(
            athlete_id,
            predictions,
            HOME_DISTANCE_CACHE_SCHEMA,
        )
    st.html(
        build_lead_coach_home_html(
            athlete_id,
            passport,
            summary,
            predictions,
            latest,
            distance_outlook,
        )
    )
