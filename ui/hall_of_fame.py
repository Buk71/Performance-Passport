import datetime
import html
import textwrap

import streamlit as st

from core.hall_of_fame import build_hall_of_fame
from ui.athlete_selection import render_athlete_selector


METRES_PER_MILE = 1609.344


def _safe_text(value):
    return html.escape(str(value or ""))


def _render_html(markup):
    st.html(textwrap.dedent(markup).strip())


def _format_clock(seconds):
    if seconds is None:
        return "--"

    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


def _format_pace_per_mile(seconds_per_km):
    if seconds_per_km is None:
        return "--"

    seconds = int(round(seconds_per_km * (METRES_PER_MILE / 1000)))
    return f"{seconds // 60}:{seconds % 60:02d}/mi"


def _format_distance_miles(distance_km):
    return f"{distance_km / (METRES_PER_MILE / 1000):.1f} mi"


def _format_date(value):
    if not value:
        return "Unknown date"

    try:
        parsed = datetime.date.fromisoformat(str(value)[:10])
        return parsed.strftime("%d %b %Y")
    except ValueError:
        return str(value)



def _format_date_with_weekday(value):
    if not value:
        return "Unknown date"

    try:
        parsed = datetime.date.fromisoformat(str(value)[:10])
        return parsed.strftime("%a %-d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def _meaningful_title(title, category, activity_date):
    text = str(title or "").strip()
    generic = {
        "",
        "run",
        "running",
        "morning run",
        "afternoon run",
        "evening run",
        "activity",
    }

    if text.lower() not in generic:
        return text

    generated = {
        "Best Easy Run Ever": "Easy Run",
        "Best Long Easy Run": "Long Easy Run",
        "Best Hot Run": "Hot-Weather Run",
        "Best Trail Run": "Trail Run",
        "Hidden Gem": "Hidden Gem Run",
    }.get(category, "Run")

    return generated


def _equipment_text(value):
    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def show_hall_of_fame_page():
    st.title("🏆 Hall of Fame")
    st.write(
        "Personal bests sit alongside the performances whose true quality "
        "only appears after adjusting for conditions."
    )

    athlete_id = render_athlete_selector(
        key="hall_of_fame_athlete_selector",
        label="Athlete",
    )

    if athlete_id is None:
        st.info("Add an athlete before building a Hall of Fame.")
        return

    hall = build_hall_of_fame(athlete_id)

    _render_html(
        f"""
        <div class="pp-card pp-card-hero pp-card-accent">
            <div class="pp-card-label">Hall of Fame</div>
            <div class="pp-card-title">
                {_safe_text(hall.headline)}
            </div>
            <div class="pp-card-copy">
                {_safe_text(hall.summary)}
            </div>
        </div>
        """
    )

    st.markdown("## 🥇 Personal Bests")

    if not hall.personal_bests:
        st.info("No standard-distance PBs could be identified yet.")
    else:
        pb_columns = st.columns(3)

        for index, pb in enumerate(hall.personal_bests):
            with pb_columns[index % 3]:
                st.markdown(f"### {pb.label}")
                st.metric("Elapsed time", _format_clock(pb.elapsed_time_s))
                st.caption(
                    f"{_format_pace_per_mile(pb.pace_s_per_km)} · "
                    f"{_format_date(pb.activity_date)}"
                )
                st.caption(pb.title)

    st.markdown("## 🌟 Greatest Performances")

    if not hall.awards:
        st.info("The coaching awards are still building.")
    else:
        for award in hall.awards:
            display_title = _meaningful_title(
                award.title,
                award.category,
                award.activity_date,
            )
            identity_parts = [
                _format_date_with_weekday(award.activity_date),
            ]

            if award.route_name:
                identity_parts.append(str(award.route_name))

            subtitle = " · ".join(
                part
                for part in identity_parts
                if part
            )

            _render_html(
                f"""
                <div class="pp-card">
                    <div class="pp-card-label">
                        {_safe_text(award.category)}
                    </div>
                    <div class="pp-card-title">
                        {_safe_text(display_title)}
                    </div>
                    <div class="pp-card-copy">
                        {_safe_text(subtitle)}
                    </div>
                    <div class="pp-card-copy">
                        {_safe_text(award.reason)}
                    </div>
                </div>
                """
            )

            columns = st.columns(4)
            columns[0].metric("Quality score", f"{award.score:.1f}/100")
            columns[1].metric(
                "Actual pace",
                _format_pace_per_mile(award.actual_pace_s_per_km),
            )
            columns[2].metric(
                "Adjusted pace",
                _format_pace_per_mile(award.equivalent_pace_s_per_km),
            )
            columns[3].metric(
                "Distance",
                _format_distance_miles(award.distance_km),
            )

            memory_parts = [
                award.environment_note,
            ]

            if award.equipment_ids:
                memory_parts.append(
                    f"Shoes/equipment: {_equipment_text(award.equipment_ids)}"
                )

            st.caption(
                " · ".join(
                    part
                    for part in memory_parts
                    if part
                )
            )

            with st.expander(f"Why {award.category.lower()}?"):
                st.write(award.reason)
                if award.avg_hr is not None:
                    st.write(f"• Average HR: {award.avg_hr:.0f} bpm")
                if award.temperature_c is not None:
                    st.write(
                        f"• Temperature: {award.temperature_c:.1f}°C"
                    )
                if award.humidity is not None:
                    st.write(f"• Humidity: {award.humidity:.0f}%")
                if award.wind_speed is not None:
                    st.write(
                        f"• Wind speed: {award.wind_speed:.0f} km/h"
                    )
                if award.elevation_m is not None:
                    st.write(
                        f"• Elevation gain: {award.elevation_m:.0f} m"
                    )
                if award.route_name:
                    st.write(f"• Route/location: {award.route_name}")
                if award.equipment_ids:
                    st.write(
                        f"• Shoes/equipment: "
                        f"{_equipment_text(award.equipment_ids)}"
                    )

            st.divider()

    with st.expander("How Hall of Fame works"):
        for limitation in hall.limitations:
            st.write(f"• {limitation}")
