"""
Developer diagnostics for Session Intelligence.

This page is intentionally transparent. It shows how activities are being
classified, why they were classified that way, and the latest identified
activity for each session type.
"""

from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from core.database import get_connection
from core.session_intelligence import ActivityFacts, classify_session


SESSION_LABELS = {
    "continuous_run": "Continuous runs",
    "structured_workout": "Structured workouts",
    "race": "Races",
    "walk": "Walks",
    "cross_training": "Cross-training",
    "unknown": "Unknown",
}


def _athlete_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()


def _get_athletes():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, first_name, last_name
        FROM athletes
        ORDER BY first_name, last_name
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "name": _athlete_name(row[1], row[2]),
        }
        for row in rows
    ]


@st.cache_data(show_spinner=False)
def _load_classified_sessions(athlete_id, data_version=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            a.id,
            a.athlete_id,
            a.activity_date,
            a.title,
            a.sport_id,
            a.distance_m,
            a.moving_time_s,
            a.elapsed_time_s,
            a.avg_hr,
            a.max_hr,
            a.elevation_up_m,
            a.temperature_c,
            a.humidity,
            a.wind_speed,
            a.route_name,
            a.raw_json,
            at.lt2_hr,
            at.max_hr
        FROM activities a
        JOIN athletes at ON at.id = a.athlete_id
        WHERE a.athlete_id = ?
        ORDER BY activity_datetime DESC
        """,
        (athlete_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    result = []

    for row in rows:
        facts = ActivityFacts(
            activity_id=row[0],
            athlete_id=row[1],
            activity_date=row[2],
            title=row[3] or "Untitled activity",
            sport_id=str(row[4]) if row[4] is not None else None,
            distance_km=float(row[5]) if row[5] is not None else None,
            moving_time_s=float(row[6]) if row[6] is not None else None,
            elapsed_time_s=float(row[7]) if row[7] is not None else None,
            avg_hr=float(row[8]) if row[8] is not None else None,
            max_hr=float(row[9]) if row[9] is not None else None,
            elevation_up_m=float(row[10]) if row[10] is not None else None,
            temperature_c=float(row[11]) if row[11] is not None else None,
            humidity=float(row[12]) if row[12] is not None else None,
            wind_speed=float(row[13]) if row[13] is not None else None,
            route_name=row[14],
            raw_json_text=row[15],
            athlete_lt2_hr=(
                float(row[16]) if row[16] is not None else None
            ),
            athlete_max_hr=(
                float(row[17]) if row[17] is not None else None
            ),
        )

        session = classify_session(facts)

        evidence_text = " | ".join(
            evidence.description
            for evidence in session.evidence
        )

        routes = ", ".join(
            route.value.replace("_", " ").title()
            for route in session.suitable_coaches
        )

        details = session.metadata.get("split_classification", {})
        scores = session.metadata.get("classification_scores", {})
        reasons_by_type = session.metadata.get(
            "classification_reasons",
            {},
        )
        split_reason = details.get("reason")
        recognition = details.get("recognition")

        result.append(
            {
                "activity_id": session.activity_id,
                "date": session.activity_date[:10]
                if session.activity_date
                else None,
                "title": session.title,
                "session_type": session.session_type.value,
                "session_label": SESSION_LABELS.get(
                    session.session_type.value,
                    session.session_type.value.replace("_", " ").title(),
                ),
                "purpose": session.purpose.value,
                "confidence": session.confidence,
                "distance_km": session.distance_km,
                "avg_hr": session.avg_hr,
                "routes": routes,
                "reason": split_reason or evidence_text or recognition,
                "recognition": recognition,
                "split_count": details.get("split_count"),
                "boundary_count": details.get("boundary_count"),
                "recovery_count": details.get("recovery_count"),
                "unknown_recovery_count": details.get(
                    "unknown_recovery_count"
                ),
                "continuous_score": scores.get("continuous_run"),
                "workout_score": scores.get("structured_workout"),
                "race_score": scores.get("race"),
                "runner_up": session.metadata.get("runner_up"),
                "score_margin": session.metadata.get("score_margin"),
                "classification_reasons": reasons_by_type,
            }
        )

    return result


def _latest_by_type(df):
    rows = []

    for session_type, label in SESSION_LABELS.items():
        subset = df[df["session_type"] == session_type]

        if subset.empty:
            rows.append(
                {
                    "Run type": label,
                    "Latest date": "None identified",
                    "Activity": "—",
                    "Confidence": "—",
                }
            )
            continue

        latest = subset.iloc[0]

        rows.append(
            {
                "Run type": label,
                "Latest date": latest["date"] or "Unknown",
                "Activity": latest["title"],
                "Confidence": f"{latest['confidence']:.0%}",
            }
        )

    return pd.DataFrame(rows)


def _get_data_version():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(MAX(id), 0),
            SUM(CASE WHEN athlete_id IS NULL THEN 1 ELSE 0 END)
        FROM activities
        """
    )

    version = cursor.fetchone()
    conn.close()

    return tuple(version)


def _get_orphan_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM activities WHERE athlete_id IS NULL"
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def show_diagnostics_page():
    st.title("🧠 Session Diagnostics")
    st.caption(
        "Developer view: inspect how Session Intelligence classifies "
        "each athlete's activity history."
    )

    athletes = _get_athletes()

    if not athletes:
        st.warning("No athletes are available.")
        return

    athlete_names = [athlete["name"] for athlete in athletes]

    selected_name = st.session_state.get(
        "selected_athlete_name",
        athlete_names[0],
    )

    if selected_name not in athlete_names:
        selected_name = athlete_names[0]

    selected_index = athlete_names.index(selected_name)

    athlete_name = st.selectbox(
        "Athlete",
        athlete_names,
        index=selected_index,
        key="diagnostics_athlete",
    )

    st.session_state.selected_athlete_name = athlete_name

    athlete = next(
        item for item in athletes if item["name"] == athlete_name
    )

    data_version = _get_data_version()

    with st.spinner("Classifying activity history..."):
        rows = _load_classified_sessions(
            athlete["id"],
            data_version,
        )

    if not rows:
        st.info("No activities are available for this athlete.")
        return

    df = pd.DataFrame(rows)

    orphan_count = _get_orphan_count()

    if orphan_count:
        st.error(
            f"{orphan_count:,} activities are not linked to an athlete. "
            "Restarting the app should repair them automatically."
        )

    st.subheader("Classification summary")

    metric_columns = st.columns(6)

    for column, (session_type, label) in zip(
        metric_columns,
        SESSION_LABELS.items(),
    ):
        count = int((df["session_type"] == session_type).sum())
        column.metric(label, f"{count:,}")

    st.subheader("Latest identified for each run type")

    st.dataframe(
        _latest_by_type(df),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Inspect classifications")

    search_text = st.text_input(
        "Find activity by date or title",
        placeholder="e.g. 2026-07-29 or Wakefield Running",
    )

    filter_columns = st.columns([1.3, 1, 1])

    with filter_columns[0]:
        type_options = ["All", *SESSION_LABELS.values()]
        selected_type = st.selectbox(
            "Session type",
            type_options,
        )

    with filter_columns[1]:
        confidence_limit = st.slider(
            "Maximum confidence",
            min_value=0.0,
            max_value=1.0,
            value=1.0,
            step=0.05,
        )

    with filter_columns[2]:
        low_confidence_only = st.checkbox(
            "Needs review only",
            value=False,
        )

    filtered = df.copy()

    if search_text.strip():
        search = search_text.strip().lower()
        filtered = filtered[
            filtered["title"].str.lower().str.contains(
                search,
                na=False,
            )
            | filtered["date"].fillna("").str.lower().str.contains(
                search,
                na=False,
            )
        ]

    if selected_type != "All":
        filtered = filtered[
            filtered["session_label"] == selected_type
        ]

    filtered = filtered[
        filtered["confidence"] <= confidence_limit
    ]

    if low_confidence_only:
        filtered = filtered[filtered["confidence"] < 0.75]

    display_df = filtered[
        [
            "date",
            "title",
            "session_label",
            "purpose",
            "confidence",
            "distance_km",
            "avg_hr",
            "continuous_score",
            "workout_score",
            "race_score",
            "runner_up",
            "routes",
            "reason",
        ]
    ].copy()

    display_df.columns = [
        "Date",
        "Activity",
        "Session type",
        "Purpose",
        "Confidence",
        "Distance km",
        "Avg HR",
        "Continuous score",
        "Workout score",
        "Race score",
        "Runner-up",
        "Coach routes",
        "Reason",
    ]

    display_df["Confidence"] = display_df["Confidence"].map(
        lambda value: f"{value:.0%}"
    )

    st.dataframe(
        display_df,
        hide_index=True,
        width="stretch",
        height=520,
    )

    st.subheader("Activity explanation")

    if filtered.empty:
        st.info("No activity matches the current filters.")
    else:
        activity_options = {
            (
                f"{row['date'] or 'Unknown'} · {row['title']} "
                f"· {row['session_label']}"
            ): int(row["activity_id"])
            for _, row in filtered.head(200).iterrows()
        }

        selected_activity_label = st.selectbox(
            "Inspect activity",
            list(activity_options.keys()),
        )
        selected_activity_id = activity_options[selected_activity_label]
        selected_row = df[
            df["activity_id"] == selected_activity_id
        ].iloc[0]

        score_cols = st.columns(3)
        score_cols[0].metric(
            "Continuous",
            f"{selected_row['continuous_score'] or 0:.1f}",
        )
        score_cols[1].metric(
            "Workout",
            f"{selected_row['workout_score'] or 0:.1f}",
        )
        score_cols[2].metric(
            "Race",
            f"{selected_row['race_score'] or 0:.1f}",
        )

        st.write(
            f"**Current classification:** "
            f"{selected_row['session_label']} "
            f"({selected_row['confidence']:.0%} confidence)"
        )
        st.write(
            f"**Runner-up:** "
            f"{str(selected_row['runner_up'] or '—').replace('_', ' ').title()}"
        )
        st.write(
            f"**Winning margin:** "
            f"{selected_row['score_margin'] or 0:.1f} points"
        )

        reason_map = selected_row["classification_reasons"] or {}

        for key, label in (
            ("continuous_run", "Continuous run"),
            ("structured_workout", "Structured workout"),
            ("race", "Race"),
        ):
            with st.expander(f"Why {label} scored this way"):
                reasons = reason_map.get(key, [])
                if reasons:
                    for reason in reasons:
                        st.write(f"• {reason}")
                else:
                    st.write("No supporting reason was recorded.")

    st.subheader("Potential classification issues")

    continuous_many_laps = df[
        (df["session_type"] == "continuous_run")
        & (df["split_count"].fillna(0) >= 8)
    ]

    structured_no_recovery = df[
        (df["session_type"] == "structured_workout")
        & (df["recovery_count"].fillna(0) == 0)
        & (df["unknown_recovery_count"].fillna(0) == 0)
    ]

    issue_left, issue_right = st.columns(2)

    with issue_left:
        st.markdown("**Continuous runs with many laps**")
        st.caption(
            "Often legitimate auto-lap long runs; useful for checking that "
            "they were not treated as workouts."
        )

        if continuous_many_laps.empty:
            st.write("None found.")
        else:
            st.dataframe(
                continuous_many_laps[
                    ["date", "title", "split_count", "reason"]
                ].head(20),
                hide_index=True,
                width="stretch",
            )

    with issue_right:
        st.markdown("**Structured sessions without recovery evidence**")
        st.caption(
            "These may be explicit title-based workouts or possible "
            "false positives."
        )

        if structured_no_recovery.empty:
            st.write("None found.")
        else:
            st.dataframe(
                structured_no_recovery[
                    ["date", "title", "confidence", "reason"]
                ].head(20),
                hide_index=True,
                width="stretch",
            )

    if st.button("Refresh diagnostics"):
        _load_classified_sessions.clear()
        st.rerun()
