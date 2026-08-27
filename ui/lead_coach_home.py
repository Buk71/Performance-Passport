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
from core.home_latest_run import build_home_latest_run
from core.home_prediction_matrix import build_home_prediction_matrix
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.activity_navigation import activity_review_url
from ui.athlete_card import image_to_data_uri
from ui.athlete_selection import render_athlete_id_selector
from ui.coaching_navigation import coaching_team_url
from ui.training_coach_navigation import training_coach_url


ROOT = Path(__file__).resolve().parent.parent
HOME_CACHE_SCHEMA = 1

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
                <div class="lc-card-kicker">Today’s run</div>
                <div class="lc-card-title">{_safe(today_title)}</div>
                <p>{_safe(today_detail)}</p>
                <div class="lc-card-meta">{_safe(today_meta)} <span>Open Training Coach →</span></div>
            </a>
            <a class="lc-focus-card lc-focus-link" href="{training_link}" target="_self">
                <div class="lc-card-kicker">Next key session</div>
                <div class="lc-card-title">{_safe(summary.next_label)}</div>
                <p>{_safe(summary.next_detail)}</p>
                <div class="lc-card-meta">{_safe(summary.next_timing)} · {_safe(summary.next_source)} <span>Full session →</span></div>
            </a>
            <{latest_wrapper} class="lc-focus-card lc-focus-link"{latest_href}>
                <div class="lc-card-kicker">Last run</div>
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
            "TC", "Training Coach", summary.week_theme,
            f"Next: {summary.next_label} · {summary.next_timing}", "training"
        ),
        (
            "RC", "Race Coach", prediction_copy,
            f"{predictions.distance_label} outlook {lead_time}", "race"
        ),
        (
            "REC", "Recovery Coach", recovery_copy,
            "Training balance, not a readiness score", "aerobic"
        ),
        (
            "NC", "Nutrition Coach",
            "Turn the training week into practical fuel, recovery meals and a shopping list.",
            "Open Fuel Planner from the navigation", None
        ),
    )
    markup = []
    for initials, title, copy, meta, coach_key in cards:
        if coach_key == "training":
            href = html.escape(training_coach_url(athlete_id), quote=True)
        else:
            href = (
                html.escape(coaching_team_url(athlete_id, coach_key), quote=True)
                if coach_key else team_url
            )
        markup.append(
            f"""
            <a class="lc-coach-card" href="{href}" target="_self">
                <div class="lc-coach-head">
                    <span class="lc-coach-mark">{_safe(initials)}</span>
                    <div><small>Specialist</small><strong>{_safe(title)}</strong></div>
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


def _prediction_matrix_table(predictions, passport) -> str:
    personal_bests = {
        pb.key: pb.all_time_seconds
        for pb in passport.personal_bests
        if pb.all_time_seconds is not None
    }
    matrix = build_home_prediction_matrix(
        predictions,
        personal_bests=personal_bests,
    )
    if not matrix.available:
        return f'<div class="lc-empty">{_safe(matrix.explanation)}</div>'

    headings = "".join(
        f'<th scope="col" class="lc-matrix-{_safe(cell.key)}">{_safe(cell.label)}</th>'
        for cell in matrix.rows[0].cells
    )
    rows = []
    for row in matrix.rows:
        active = '<span class="lc-active-distance">Active</span>' if row.is_active_distance else ""
        cells = "".join(
            f'<td class="lc-matrix-{_safe(cell.key)}"><strong>{_clock(cell.seconds)}</strong></td>'
            for cell in row.cells
        )
        rows.append(
            f"""
            <tr class="{'lc-active-row' if row.is_active_distance else ''}">
                <th scope="row"><strong>{_safe(row.label)}</strong>{active}<small>{row.distance_km:g} km</small></th>
                {cells}
            </tr>
            """
        )

    return f"""
        <div class="lc-matrix-wrap">
            <table class="lc-matrix">
                <thead><tr><th scope="col">Distance</th>{headings}</tr></thead>
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
    target = _clock(summary.target_time_s)
    aerobic = (
        f"{passport.aerobic_trend_percent:+.1f}%"
        if passport.aerobic_trend_percent is not None else "—"
    )
    age_grade = (
        f"{passport.age_grade_all_time:.1f}%"
        if passport.age_grade_all_time is not None else "—"
    )
    team_url = html.escape(coaching_team_url(athlete_id), quote=True)

    return f"""
    <main class="lc-home">
        <section class="lc-passport">
            <div class="lc-photo-shell">{_passport_photo(passport)}</div>
            <div class="lc-passport-copy">
                <div class="lc-eyebrow"><span></span>Athlete passport · Live profile</div>
                <h1>{_safe(passport.full_name)}</h1>
                <div class="lc-category">{_safe(passport.category)}</div>
                <div class="lc-pb-grid">{_passport_pbs(passport)}</div>
            </div>
            <div class="lc-potential">
                <div class="lc-potential-label">Current {_safe(predictions.distance_label)} potential</div>
                <div class="lc-potential-range">{_safe(range_text)}</div>
                <div class="lc-potential-central">Central view <strong>{_clock(predictions.central_seconds)}</strong></div>
                <div class="lc-potential-grid">
                    <div><span>Age grade</span><strong>{_safe(age_grade)}</strong></div>
                    <div><span>Goal</span><strong>{_safe(target)}</strong></div>
                    <div><span>Confidence</span><strong>{_safe(confidence)}</strong></div>
                    <div><span>Aerobic direction</span><strong>{_safe(aerobic)}</strong></div>
                </div>
            </div>
        </section>

        <section class="lc-briefing">
            <div class="lc-briefing-mark">LC</div>
            <div class="lc-briefing-copy">
                <div class="lc-eyebrow lc-dark"><span></span>Lead Coach briefing</div>
                <h2>{_safe(headline)}</h2>
                <p>{_safe(briefing)}</p>
                <div class="lc-briefing-meta">
                    <span>{_safe(summary.goal_name)}</span>
                    <span>{_safe(summary.block_name)}</span>
                    <span>{_safe(summary.block_context)}</span>
                </div>
            </div>
            <a href="{team_url}" target="_self" class="lc-primary-action">Open coaching room <b>→</b></a>
        </section>

        {_focus_cards(athlete_id, summary, latest)}

        <section class="lc-section">
            <div class="lc-section-heading">
                <div><div class="lc-eyebrow lc-dark"><span></span>Your coaching team</div><h2>One athlete. Several useful perspectives.</h2></div>
                <a href="{team_url}" target="_self">See the evidence behind every opinion →</a>
            </div>
            <div class="lc-coach-grid">{_coach_cards(athlete_id, summary, predictions)}</div>
        </section>

        <section class="lc-section lc-week-section">
            <div class="lc-section-heading">
                <div><div class="lc-eyebrow lc-dark"><span></span>This week</div><h2>{_safe(summary.week_theme)}</h2></div>
                <div class="lc-source">{_safe(summary.next_source)}</div>
            </div>
            <div class="lc-week-grid">{_week_strip(summary)}</div>
        </section>

        <section class="lc-section lc-outlook-section">
            <div class="lc-section-heading">
                <div><div class="lc-eyebrow lc-dark"><span></span>Race Coach outlook</div><h2>Capability in the conditions that change race day.</h2></div>
                <div class="lc-source">Four distances · six race environments</div>
            </div>
            <div class="lc-opinion-grid">{_coach_opinions(athlete_id, predictions)}</div>
            {_prediction_matrix_table(predictions, passport)}
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
            .lc-home {{ --navy:#08253e; --navy2:#0d3653; --ink:#10273d; --muted:#607181; --orange:#f15a2a; --green:#279675; --cream:#f7f4ee; color:var(--ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
            .lc-home * {{ box-sizing:border-box; }}
            .lc-home a {{ color:inherit; text-decoration:none; }}
            .lc-passport {{ position:relative; display:grid; grid-template-columns:220px minmax(360px,1.1fr) minmax(350px,.9fr); min-height:278px; overflow:hidden; border:1px solid rgba(255,255,255,.12); border-radius:28px; background:radial-gradient(circle at 86% 20%,rgba(56,151,145,.28),transparent 31%),linear-gradient(125deg,#071f36 0%,#0a2e4b 56%,#0c4256 100%); box-shadow:0 24px 55px rgba(10,33,53,.18); color:#fff; }}
            .lc-passport:after {{ content:""; position:absolute; right:-120px; bottom:-220px; width:480px; height:480px; border:54px solid rgba(255,255,255,.04); border-radius:50%; }}
            .lc-photo-shell {{ position:relative; min-height:278px; overflow:hidden; background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(0,0,0,.18)); }}
            .lc-athlete-photo {{ width:100%; height:100%; object-fit:cover; object-position:center 25%; filter:saturate(.92) contrast(1.04); }}
            .lc-photo-shell:after {{ content:""; position:absolute; inset:0; background:linear-gradient(90deg,transparent 65%,#08243d 100%); }}
            .lc-photo-fallback {{ display:grid; place-items:center; height:100%; font-size:54px; font-weight:900; color:rgba(255,255,255,.5); }}
            .lc-passport-copy {{ position:relative; z-index:1; padding:29px 28px 26px 26px; }}
            .lc-eyebrow {{ display:flex; align-items:center; gap:10px; color:#8ee2c4; font-size:12px; font-weight:850; letter-spacing:.17em; text-transform:uppercase; }}
            .lc-eyebrow span {{ width:28px; height:3px; border-radius:999px; background:var(--orange); }}
            .lc-eyebrow.lc-dark {{ color:#6a7987; }}
            .lc-passport h1 {{ margin:11px 0 0; font-size:45px; line-height:.98; letter-spacing:-.045em; }}
            .lc-category {{ margin-top:8px; color:#c6d2dc; font-size:14px; font-weight:750; letter-spacing:.12em; text-transform:uppercase; }}
            .lc-pb-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:28px; }}
            .lc-pb {{ min-width:0; padding:11px 12px; border:1px solid rgba(255,255,255,.12); border-radius:13px; background:rgba(255,255,255,.055); }}
            .lc-pb span,.lc-pb small {{ display:block; color:#aabac7; font-size:10px; font-weight:800; letter-spacing:.09em; text-transform:uppercase; }}
            .lc-pb strong {{ display:block; margin-top:3px; color:#fff; font-size:20px; }}
            .lc-pb small {{ margin-top:4px; font-size:8px; letter-spacing:.02em; text-transform:none; }}
            .lc-potential {{ position:relative; z-index:1; align-self:stretch; margin:20px; padding:22px 24px; border:1px solid rgba(255,255,255,.16); border-radius:20px; background:rgba(255,255,255,.09); backdrop-filter:blur(8px); }}
            .lc-potential-label {{ color:#a9c0ce; font-size:11px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; }}
            .lc-potential-range {{ margin-top:8px; font-size:38px; line-height:1; font-weight:900; letter-spacing:-.04em; }}
            .lc-potential-central {{ margin-top:8px; color:#a8c7c2; font-size:13px; }}
            .lc-potential-central strong {{ color:#8be0bd; }}
            .lc-potential-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:19px; padding-top:16px; border-top:1px solid rgba(255,255,255,.13); }}
            .lc-potential-grid span,.lc-potential-grid strong {{ display:block; }}
            .lc-potential-grid span {{ color:#91a7b7; font-size:9px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }}
            .lc-potential-grid strong {{ margin-top:3px; color:#fff; font-size:14px; line-height:1.2; }}
            .lc-briefing {{ display:grid; grid-template-columns:auto minmax(0,1fr) auto; align-items:center; gap:20px; margin-top:18px; padding:26px 28px; border:1px solid #ded8cf; border-left:5px solid var(--orange); border-radius:21px; background:#fff; box-shadow:0 13px 35px rgba(36,44,50,.075); }}
            .lc-briefing-mark {{ display:grid; place-items:center; width:58px; height:58px; border-radius:18px; background:var(--navy); color:#fff; font-size:18px; font-weight:900; }}
            .lc-briefing h2,.lc-section h2,.lc-daily h2 {{ margin:6px 0 0; font-size:28px; line-height:1.08; letter-spacing:-.035em; }}
            .lc-briefing p {{ margin:7px 0 0; color:var(--muted); font-size:15px; line-height:1.45; }}
            .lc-briefing-meta {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:12px; }}
            .lc-briefing-meta span {{ padding:6px 9px; border-radius:999px; background:#f4f0ea; color:#526575; font-size:10px; font-weight:750; }}
            .lc-primary-action {{ display:flex; align-items:center; gap:16px; padding:14px 16px 14px 19px; border-radius:14px; background:var(--navy); color:#fff!important; font-size:13px; font-weight:850; white-space:nowrap; }}
            .lc-primary-action b {{ display:grid; place-items:center; width:28px; height:28px; border-radius:9px; background:var(--orange); font-size:16px; }}
            .lc-focus-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:13px; margin-top:13px; }}
            .lc-focus-card {{ display:flex; min-height:172px; flex-direction:column; padding:21px; border:1px solid #dfd9d0; border-radius:19px; background:#fff; box-shadow:0 10px 28px rgba(36,44,50,.06); }}
            .lc-focus-today {{ background:linear-gradient(145deg,#fff7f0,#fff); border-color:#f1c4ae; }}
            .lc-card-kicker {{ color:#798896; font-size:11px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; }}
            .lc-card-title {{ margin-top:8px; font-size:23px; font-weight:900; letter-spacing:-.03em; }}
            .lc-focus-card p {{ margin:7px 0 12px; color:var(--muted); font-size:14px; line-height:1.4; }}
            .lc-card-meta {{ margin-top:auto; color:#607181; font-size:11px; font-weight:750; }}
            .lc-card-meta span {{ float:right; color:var(--green); }}
            .lc-focus-link {{ transition:transform .16s ease,box-shadow .16s ease; }}
            .lc-focus-link:hover,.lc-coach-card:hover,.lc-opinion:hover {{ transform:translateY(-2px); box-shadow:0 15px 32px rgba(11,38,60,.11); }}
            .lc-section {{ margin-top:20px; padding:27px; border:1px solid #ded8cf; border-radius:23px; background:#fff; box-shadow:0 14px 36px rgba(36,44,50,.065); }}
            .lc-section-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:24px; }}
            .lc-section-heading>a {{ color:var(--green); font-size:12px; font-weight:850; }}
            .lc-source {{ max-width:360px; color:#748390; font-size:11px; font-weight:700; text-align:right; }}
            .lc-coach-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:11px; margin-top:20px; }}
            .lc-coach-card {{ display:flex; min-height:213px; flex-direction:column; padding:18px; border:1px solid #e3ddd5; border-radius:17px; background:#faf8f4; transition:transform .16s ease,box-shadow .16s ease; }}
            .lc-coach-head {{ display:flex; align-items:center; gap:11px; }}
            .lc-coach-mark {{ display:grid; place-items:center; width:43px; height:43px; border-radius:13px; background:var(--navy); color:#fff; font-size:12px; font-weight:900; }}
            .lc-coach-head small,.lc-coach-head strong {{ display:block; }}
            .lc-coach-head small {{ color:#82909c; font-size:8px; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
            .lc-coach-head strong {{ margin-top:2px; font-size:16px; }}
            .lc-arrow {{ margin-left:auto; color:var(--green); font-weight:900; }}
            .lc-coach-card p {{ margin:17px 0 12px; color:#536777; font-size:13px; line-height:1.45; }}
            .lc-coach-meta {{ margin-top:auto; padding-top:12px; border-top:1px solid #e2ddd5; color:#213c53; font-size:11px; font-weight:800; }}
            .lc-week-section {{ background:#fbfaf7; }}
            .lc-week-grid {{ display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:7px; margin-top:19px; }}
            .lc-week-day {{ min-width:0; min-height:135px; padding:13px 12px; border:1px solid #e2ddd5; border-radius:14px; background:#fff; }}
            .lc-day-head {{ display:flex; justify-content:space-between; color:#798895; font-size:10px; font-weight:850; letter-spacing:.13em; text-transform:uppercase; }}
            .lc-day-head i {{ width:7px; height:7px; border-radius:50%; background:#d9dce0; }}
            .lc-week-day strong {{ display:block; margin-top:9px; font-size:14px; line-height:1.15; }}
            .lc-week-day p {{ display:-webkit-box; overflow:hidden; margin:6px 0; color:#617281; font-size:10px; line-height:1.3; -webkit-box-orient:vertical; -webkit-line-clamp:3; }}
            .lc-week-day small {{ color:#738593; font-size:9px; font-weight:750; }}
            .lc-day-today {{ border:2px solid var(--orange); background:#fff7f1; box-shadow:0 7px 17px rgba(241,90,42,.12); }}
            .lc-day-today .lc-day-head i {{ background:var(--orange); }}
            .lc-day-completed {{ background:#eef8f3; border-color:#b7dfcf; }}
            .lc-day-completed .lc-day-head i {{ background:var(--green); }}
            .lc-outlook-section {{ background:linear-gradient(180deg,#fff,#faf8f4); }}
            .lc-opinion-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:20px; }}
            .lc-opinion {{ padding:16px; border:1px solid #ded8cf; border-top:4px solid #aeb9c1; border-radius:15px; background:#fff; transition:transform .16s ease,box-shadow .16s ease; }}
            .lc-opinion-optimistic {{ border-top-color:var(--green); }} .lc-opinion-cautious {{ border-top-color:var(--orange); }}
            .lc-opinion-top {{ display:flex; align-items:center; justify-content:space-between; color:#697987; font-size:11px; font-weight:850; text-transform:uppercase; }}
            .lc-lead-tag {{ padding:4px 7px; border-radius:999px; background:var(--orange); color:#fff; font-size:8px; }}
            .lc-opinion-time {{ margin-top:8px; font-size:30px; font-weight:900; letter-spacing:-.04em; }}
            .lc-opinion-bottom {{ display:flex; justify-content:space-between; margin-top:8px; color:#617281; font-size:10px; }}
            .lc-opinion-bottom strong {{ color:#244058; }}
            .lc-matrix-wrap {{ overflow-x:auto; margin-top:12px; border:1px solid #ded8cf; border-radius:16px; background:#fff; }}
            .lc-matrix {{ width:100%; min-width:830px; border-collapse:collapse; }}
            .lc-matrix th,.lc-matrix td {{ padding:14px 13px; border-right:1px solid #e5e0d8; border-bottom:1px solid #e5e0d8; text-align:left; }}
            .lc-matrix tr:last-child th,.lc-matrix tr:last-child td {{ border-bottom:0; }}
            .lc-matrix th:last-child,.lc-matrix td:last-child {{ border-right:0; }}
            .lc-matrix thead th {{ background:#f2f0eb; color:#687987; font-size:10px; font-weight:850; letter-spacing:.08em; text-transform:uppercase; white-space:nowrap; }}
            .lc-matrix thead th:first-child {{ background:var(--navy); color:#fff; }}
            .lc-matrix tbody th {{ position:relative; min-width:132px; background:#faf8f4; }}
            .lc-matrix tbody th strong,.lc-matrix tbody th small {{ display:block; }}
            .lc-matrix tbody th strong {{ font-size:17px; }}
            .lc-matrix tbody th small {{ margin-top:3px; color:#798895; font-size:9px; }}
            .lc-matrix td strong {{ font-size:17px; letter-spacing:-.025em; white-space:nowrap; }}
            .lc-matrix-ideal {{ background:#fff8ee!important; }}
            .lc-matrix-typical {{ background:#f0f8f4!important; }}
            .lc-matrix-trail {{ background:#f4f7f1!important; }}
            .lc-active-row th {{ box-shadow:inset 4px 0 0 var(--orange); }}
            .lc-active-distance {{ position:absolute; top:11px; right:9px; padding:3px 6px; border-radius:999px; background:var(--orange); color:#fff; font-size:7px; font-weight:900; letter-spacing:.06em; text-transform:uppercase; }}
            .lc-matrix-note {{ margin-top:9px; color:#687987; font-size:10px; line-height:1.4; }}
            .lc-matrix-note strong {{ color:#314b60; }}
            .lc-daily {{ display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:21px; margin:20px 0 8px; padding:26px 29px; overflow:hidden; border-radius:22px; background:radial-gradient(circle at 90% 10%,rgba(47,162,132,.23),transparent 30%),linear-gradient(120deg,#08243d,#0c3852); color:#fff; box-shadow:0 18px 40px rgba(8,36,61,.15); }}
            .lc-daily-number {{ display:grid; place-items:center; width:70px; height:70px; border:1px solid rgba(255,255,255,.2); border-radius:20px; background:rgba(255,255,255,.08); font-size:29px; font-weight:900; }}
            .lc-daily p {{ margin:7px 0 0; max-width:800px; color:#c3d0d9; font-size:14px; line-height:1.45; }}
            .lc-daily-date {{ color:#a9bbc8; font-size:11px; font-weight:750; text-align:right; }}
            .lc-daily-date strong {{ display:block; margin-top:3px; color:#fff; font-size:14px; }}
            .lc-empty {{ padding:20px; color:#687987; }}
            .lc-home a:focus-visible {{ outline:3px solid rgba(241,90,42,.65); outline-offset:3px; }}
            @media (max-width:1180px) {{
                .lc-passport {{ grid-template-columns:180px 1fr; }} .lc-potential {{ grid-column:1/-1; margin:0 18px 18px; }}
                .lc-coach-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
                .lc-week-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
            }}
            @media (max-width:760px) {{
                .lc-passport {{ display:block; }} .lc-photo-shell {{ height:220px; }} .lc-passport-copy {{ padding:22px; }} .lc-passport h1 {{ font-size:36px; }}
                .lc-pb-grid {{ margin-top:20px; }} .lc-potential-range {{ font-size:32px; }}
                .lc-briefing {{ grid-template-columns:auto 1fr; padding:21px; }} .lc-primary-action {{ grid-column:1/-1; justify-content:space-between; }}
                .lc-focus-grid,.lc-opinion-grid {{ grid-template-columns:1fr; }} .lc-coach-grid {{ grid-template-columns:1fr; }}
                .lc-section {{ padding:21px; }} .lc-section-heading {{ align-items:flex-start; flex-direction:column; }} .lc-source {{ text-align:left; }}
                .lc-week-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
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
    st.html(
        build_lead_coach_home_html(
            athlete_id,
            passport,
            summary,
            predictions,
            latest,
        )
    )
