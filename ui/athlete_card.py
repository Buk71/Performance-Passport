import base64
import html
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from core.athlete_passport import build_athlete_passport
from core.database import get_connection
from ui.athlete_selection import render_athlete_selector


LOGO_PATH = ROOT / "assets" / "brand" / "pp_logo.png"


def image_to_data_uri(path: Path) -> str:
    if not path.exists():
        return ""

    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "image/png")

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def _default_athlete_id() -> int | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM athletes ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def _athlete_photo_path(first_name: str, last_name: str) -> Path | None:
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


def _format_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"

    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    remaining = total % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


def _format_grade(value: float | None) -> str:
    return f"{value:.1f}%" if value is not None else "—"


def _format_trend(value: float | None) -> str:
    return f"{value:+.1f}%" if value is not None else "—"


def _chart_paths(points: tuple[float, ...]) -> tuple[str, str, float, float]:
    values = points or (50.0,) * 12
    step = 900.0 / max(len(values) - 1, 1)
    coordinates = [
        (round(index * step, 2), round(value, 2))
        for index, value in enumerate(values)
    ]
    line_path = " ".join(
        ("M" if index == 0 else "L") + f"{x},{y}"
        for index, (x, y) in enumerate(coordinates)
    )
    fill_path = f"{line_path} L900,110 L0,110 Z"
    last_x, last_y = coordinates[-1]
    return line_path, fill_path, last_x, last_y


def build_athlete_card_html(athlete_id: int | None = None) -> str:
    athlete_id = athlete_id or _default_athlete_id()
    passport = (
        build_athlete_passport(athlete_id)
        if athlete_id is not None
        else None
    )

    if passport is None:
        return "<p>No athlete data is available yet.</p>"

    photo_path = _athlete_photo_path(
        passport.first_name,
        passport.last_name,
    )
    photo_uri = image_to_data_uri(photo_path) if photo_path else ""
    logo_uri = image_to_data_uri(LOGO_PATH)

    safe_name = html.escape(passport.full_name)
    safe_category = html.escape(passport.category)
    safe_initials = html.escape(passport.initials)

    photo_html = (
        f'<img class="pp-photo" src="{photo_uri}" alt="{safe_name}">'
        if photo_uri
        else f'<div class="pp-photo-placeholder">{safe_initials}</div>'
    )

    logo_html = (
        f'<img class="pp-logo" src="{logo_uri}" alt="Performance Passport">'
        if logo_uri
        else '<div class="pp-logo-fallback">PP</div>'
    )

    pb_rows = "".join(
        f"""
        <div class="pb-row">
            <div class="pb-event">{html.escape(pb.label)}</div>
            <div class="pb-time">{_format_time(pb.all_time_seconds)}</div>
            <div class="pb-time recent">{
                _format_time(pb.last_12_months_seconds)
            }</div>
        </div>
        """
        for pb in passport.personal_bests
    )

    line_path, fill_path, last_x, last_y = _chart_paths(
        passport.aerobic_chart_points
    )
    trend_text = _format_trend(passport.aerobic_trend_percent)
    trend_class = (
        "positive"
        if passport.aerobic_trend_percent is not None
        and passport.aerobic_trend_percent >= 0
        else "negative"
    )

    return f"""
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
        }}

        .pp-shell {{
            width: 100%;
            max-width: 460px;
            margin: 0 auto;
            font-family:
                Inter,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }}

        .pp-passport {{
            position: relative;
            overflow: hidden;
            width: 100%;
            background:
                radial-gradient(
                    circle at 82% 12%,
                    rgba(34, 104, 165, 0.22),
                    transparent 30%
                ),
                linear-gradient(
                    145deg,
                    #07182a 0%,
                    #0b2239 52%,
                    #102e49 100%
                );
            color: #ffffff;
            border-radius: 20px;
            border: 1px solid rgba(240, 90, 40, 0.52);
            box-shadow:
                0 22px 56px rgba(7, 24, 42, 0.20),
                inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }}

        .pp-top {{
            display: grid;
            grid-template-columns: minmax(0, 1.12fr) minmax(170px, 0.88fr);
            min-height: 230px;
        }}

        .pp-identity {{
            position: relative;
            z-index: 2;
            padding: 18px 16px 18px 20px;
        }}

        .pp-logo {{
            display: block;
            width: 135px;
            max-width: 64%;
            height: 65px;
            object-fit: contain;
            object-position: left center;
            margin: -2px 0 8px -2px;
        }}

        .pp-logo-fallback {{
            color: #ff5a22;
            font-size: 42px;
            font-weight: 900;
            margin-bottom: 24px;
        }}

        .pp-eyebrow {{
            margin-bottom: 6px;
            color: #ff6533;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }}

        .pp-name {{
            margin: 0;
            font-size: clamp(25px, 6vw, 31px);
            line-height: 0.98;
            font-weight: 850;
            letter-spacing: -0.045em;
        }}

        .pp-category {{
            margin-top: 8px;
            color: #b8c6d5;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }}

        .pp-motto {{
            margin-top: 15px;
            max-width: 225px;
            color: #d6e0e9;
            font-size: 10.5px;
            line-height: 1.42;
        }}

        .pp-motto strong {{
            color: #ffffff;
        }}

        .pp-photo-wrap {{
            position: relative;
            min-height: 230px;
            overflow: hidden;
        }}

        .pp-photo {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: 52% 26%;
        }}

        .pp-photo-placeholder {{
            height: 100%;
            min-height: 230px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 52px;
            font-weight: 900;
            color: rgba(255,255,255,.25);
        }}

        .pp-photo-wrap::before {{
            content: "";
            position: absolute;
            z-index: 1;
            inset: 0;
            background:
                linear-gradient(
                    90deg,
                    #0b233b 0%,
                    rgba(11, 35, 59, 0.28) 23%,
                    transparent 58%
                ),
                linear-gradient(
                    0deg,
                    rgba(7, 24, 42, 0.56) 0%,
                    transparent 38%
                );
        }}

        .pp-stats {{
            display: grid;
            grid-template-columns: 0.86fr 1.14fr;
            gap: 1px;
            background: rgba(255,255,255,0.10);
            border-top: 1px solid rgba(255,255,255,0.10);
        }}

        .pp-panel {{
            background: rgba(7, 24, 42, 0.92);
            padding: 15px 13px 14px;
        }}

        .pp-section-title {{
            margin-bottom: 11px;
            color: #91a3b5;
            font-size: 8px;
            font-weight: 850;
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }}

        .pp-grade-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 7px;
        }}

        .pp-grade + .pp-grade {{
            padding-left: 7px;
            border-left: 1px solid rgba(255,255,255,0.12);
        }}

        .pp-grade-value {{
            font-size: 23px;
            line-height: 1;
            font-weight: 850;
            letter-spacing: -0.04em;
            color: #ffffff;
        }}

        .pp-grade-value.orange {{
            color: #ff6533;
        }}

        .pp-grade-label {{
            margin-top: 6px;
            color: #9badbe;
            font-size: 7px;
            line-height: 1.35;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .pb-header,
        .pb-row {{
            display: grid;
            grid-template-columns: 0.58fr 0.96fr 1fr;
            align-items: center;
            column-gap: 5px;
        }}

        .pb-header {{
            padding-bottom: 6px;
            color: #8094a8;
            font-size: 7px;
            font-weight: 850;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }}

        .pb-row {{
            min-height: 28px;
            border-top: 1px solid rgba(255,255,255,0.08);
        }}

        .pb-event {{
            color: #a9b9c8;
            font-size: 9px;
            font-weight: 800;
        }}

        .pb-time {{
            color: #ffffff;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: -0.02em;
        }}

        .pb-time.recent {{
            color: #7dd9ad;
        }}

        .pp-development {{
            position: relative;
            padding: 15px 16px 12px;
            background: #0a2036;
            border-top: 1px solid rgba(255,255,255,0.10);
        }}

        .development-head {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-end;
        }}

        .development-title {{
            margin: 0;
            color: #ffffff;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: -0.025em;
        }}

        .development-copy {{
            margin-top: 4px;
            color: #8fa2b5;
            font-size: 9px;
        }}

        .development-score {{
            text-align: right;
            color: #78d9a8;
            font-size: 20px;
            line-height: 1;
            font-weight: 850;
            letter-spacing: -0.03em;
        }}

        .development-score.negative {{
            color: #ff9a76;
        }}

        .development-score span {{
            display: block;
            margin-top: 4px;
            color: #8296a9;
            font-size: 7px;
            font-weight: 800;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }}

        .chart {{
            width: 100%;
            height: 64px;
            margin-top: 8px;
        }}

        .chart-grid {{
            stroke: rgba(255,255,255,0.07);
            stroke-width: 1;
        }}

        .chart-fill {{
            fill: url(#areaGradient);
        }}

        .chart-line {{
            fill: none;
            stroke: #ff6433;
            stroke-width: 4;
            stroke-linecap: round;
            stroke-linejoin: round;
        }}

        .chart-dot {{
            fill: #ff6433;
            stroke: #0a2036;
            stroke-width: 4;
        }}

        @media (max-width: 410px) {{
            .pp-shell {{
                max-width: 100%;
            }}

            .pp-passport {{
                border-radius: 20px;
            }}

            .pp-top {{
                position: relative;
                display: block;
                min-height: 410px;
            }}

            .pp-photo-wrap {{
                position: absolute;
                inset: 0;
                min-height: 410px;
            }}

            .pp-photo {{
                object-position: 55% 24%;
            }}

            .pp-photo-wrap::before {{
                background:
                    linear-gradient(
                        180deg,
                        rgba(7,24,42,.18) 0%,
                        rgba(7,24,42,.56) 52%,
                        #07182a 100%
                    ),
                    linear-gradient(
                        90deg,
                        rgba(7,24,42,.88) 0%,
                        rgba(7,24,42,.58) 58%,
                        rgba(7,24,42,.18) 100%
                    );
            }}

            .pp-identity {{
                position: relative;
                z-index: 3;
                padding: 20px 22px 24px;
                min-height: 410px;
                display: flex;
                flex-direction: column;
                justify-content: flex-end;
            }}

            .pp-logo {{
                position: absolute;
                left: 20px;
                top: 14px;
                width: 150px;
                max-width: 48%;
                height: 82px;
                margin: 0;
            }}

            .pp-eyebrow {{
                font-size: 10px;
                margin-bottom: 6px;
            }}

            .pp-name {{
                font-size: clamp(30px, 9vw, 42px);
            }}

            .pp-category {{
                font-size: 11px;
                margin-top: 8px;
            }}

            .pp-motto {{
                margin-top: 18px;
                max-width: 88%;
                font-size: 13px;
                line-height: 1.42;
            }}

            .pp-stats {{
                grid-template-columns: 1fr;
            }}

            .pp-panel {{
                padding: 22px;
            }}

            .pp-grade-grid {{
                gap: 12px;
            }}

            .pp-grade + .pp-grade {{
                padding-left: 12px;
            }}

            .pp-grade-value {{
                font-size: 32px;
            }}

            .pb-time {{
                font-size: 15px;
            }}

            .pp-development {{
                padding: 22px;
            }}

            .development-head {{
                align-items: flex-start;
            }}

            .development-title {{
                font-size: 18px;
            }}

            .development-score {{
                font-size: 23px;
            }}

            .chart {{
                height: 86px;
            }}
        }}

        @media (max-width: 440px) {{
            .pp-top {{
                min-height: 370px;
            }}

            .pp-photo-wrap {{
                min-height: 370px;
            }}

            .pp-identity {{
                min-height: 370px;
            }}

            .pp-motto {{
                max-width: 100%;
                font-size: 12px;
            }}

            .pp-grade-value {{
                font-size: 28px;
            }}

            .pb-header,
            .pb-row {{
                grid-template-columns: 0.62fr 1fr 1fr;
                column-gap: 8px;
            }}

            .pb-time {{
                font-size: 14px;
            }}

            .development-head {{
                display: block;
            }}

            .development-score {{
                margin-top: 12px;
                text-align: left;
            }}
        }}
    </style>

    <div class="pp-shell">
        <article class="pp-passport">

            <section class="pp-top">

                <div class="pp-identity">
                    {logo_html}

                    <div class="pp-eyebrow">Athlete Passport</div>

                    <h1 class="pp-name">{safe_name}</h1>

                    <div class="pp-category">
                        {safe_category.replace(' · ', ' &nbsp;·&nbsp; ')}
                    </div>

                    <div class="pp-motto">
                        <strong>Every run has something to give.</strong><br>
                        Your record of progress, built on data and guided by coaching.
                    </div>
                </div>

                <div class="pp-photo-wrap">
                    {photo_html}
                </div>

            </section>

            <section class="pp-stats">

                <div class="pp-panel">
                    <div class="pp-section-title">Age graded performance</div>

                    <div class="pp-grade-grid">
                        <div class="pp-grade">
                            <div class="pp-grade-value orange">{
                                _format_grade(passport.age_grade_all_time)
                            }</div>
                            <div class="pp-grade-label">Best<br>all time</div>
                        </div>

                        <div class="pp-grade">
                            <div class="pp-grade-value">{
                                _format_grade(
                                    passport.age_grade_last_12_months
                                )
                            }</div>
                            <div class="pp-grade-label">Best<br>last 12 months</div>
                        </div>
                    </div>
                </div>

                <div class="pp-panel">
                    <div class="pp-section-title">Personal bests</div>

                    <div class="pb-header">
                        <div>Event</div>
                        <div>All time</div>
                        <div>12 months</div>
                    </div>

                    {pb_rows}
                </div>

            </section>

            <section class="pp-development">

                <div class="development-head">
                    <div>
                        <div class="pp-section-title" style="margin-bottom:8px;">
                            Aerobic development
                        </div>

                        <h2 class="development-title">
                            Fitness that survives the calendar.
                        </h2>

                        <div class="development-copy">
                            Easy-run efficiency · rolling 12 months
                        </div>
                    </div>

                    <div class="development-score {trend_class}">
                        {trend_text}
                        <span>12 month trend</span>
                    </div>
                </div>

                <svg
                    class="chart"
                    viewBox="0 0 900 110"
                    preserveAspectRatio="none"
                    aria-label="Aerobic development trend"
                >
                    <defs>
                        <linearGradient
                            id="areaGradient"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                        >
                            <stop
                                offset="0%"
                                stop-color="#ff6433"
                                stop-opacity="0.24"
                            />
                            <stop
                                offset="100%"
                                stop-color="#ff6433"
                                stop-opacity="0"
                            />
                        </linearGradient>
                    </defs>

                    <line class="chart-grid" x1="0" y1="25" x2="900" y2="25"/>
                    <line class="chart-grid" x1="0" y1="55" x2="900" y2="55"/>
                    <line class="chart-grid" x1="0" y1="85" x2="900" y2="85"/>

                    <path
                        class="chart-fill"
                        d="{fill_path}"
                    />

                    <path
                        class="chart-line"
                        d="{line_path}"
                    />

                    <circle
                        class="chart-dot"
                        cx="{last_x}"
                        cy="{last_y}"
                        r="6"
                    />
                </svg>

            </section>

        </article>
    </div>
    """


def render_athlete_card(athlete_id: int | None = None):
    st.html(build_athlete_card_html(athlete_id))


if __name__ == "__main__":
    st.set_page_config(
        page_title="Performance Passport · Athlete Card",
        layout="wide",
    )

    st.markdown(
        """
        <style>
            .block-container {
                max-width: 520px;
                padding-top: 2rem;
                padding-bottom: 3rem;
            }

            [data-testid="stHeader"] {
                background: transparent;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    athlete_id = render_athlete_selector(
        key="athlete_card_selector",
        label="Athlete",
        label_visibility="collapsed",
    )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
    else:
        render_athlete_card(athlete_id)
