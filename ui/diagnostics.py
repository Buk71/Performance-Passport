"""
Developer diagnostics for Session Intelligence.

This page is intentionally transparent. It shows how activities are being
classified, why they were classified that way, and the latest identified
activity for each session type.
"""

from __future__ import annotations

import datetime
import html

import pandas as pd
import streamlit as st

from core.database import get_connection
from core.recognition_audit import RecognitionAuditReport, build_recognition_audit
from core.session_intelligence import ActivityFacts, classify_session
from ui.activity_navigation import activity_review_url


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


@st.cache_data(show_spinner=False)
def _load_recognition_audit(athlete_id, data_version=None):
    """Keep the review layer read-only and independent of coach predictions."""
    del data_version
    return build_recognition_audit(int(athlete_id))


def build_recognition_audit_html(report: RecognitionAuditReport) -> str:
    """Render the audit overview without suggesting unapproved live changes."""
    athlete_name = html.escape(report.athlete_name)
    return f"""
    <section class="pp-ra-shell">
      <div class="pp-ra-heading">
        <div>
          <span class="pp-ra-eyebrow">HISTORICAL RECOGNITION AUDIT</span>
          <h2>{athlete_name} · every run, independently checked</h2>
          <p>Physical lap evidence is compared against the current classification.
             Nothing here changes your history, predictions or coaching decisions.</p>
        </div>
        <span class="pp-ra-badge">READ-ONLY PREVIEW</span>
      </div>
      <div class="pp-ra-metrics">
        <article><span>RUNNING ACTIVITIES</span><strong>{report.total_running_activities:,}</strong></article>
        <article><span>LIKELY MISSED WORKOUTS</span><strong>{report.likely_missed_workout_count:,}</strong></article>
        <article><span>LIKELY FALSE WORKOUTS</span><strong>{report.likely_false_workout_count:,}</strong></article>
        <article><span>STRIDES / PICKUPS PROTECTED</span><strong>{report.protected_strides_count + report.protected_pickups_count:,}</strong></article>
        <article><span>ACTIVITIES TO REVIEW</span><strong>{report.reviewed_count:,}</strong></article>
      </div>
    </section>
    <style>
      .pp-ra-shell {{margin:18px 0 24px;padding:23px 25px;border:1px solid #e8e3da;
        border-top:3px solid #238a52;border-radius:19px;background:#fffdf9;}}
      .pp-ra-heading {{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;}}
      .pp-ra-eyebrow {{color:#238a52;font-size:12px;font-weight:850;letter-spacing:.12em;}}
      .pp-ra-heading h2 {{margin:7px 0 6px;color:#10263d!important;font-size:26px;
        line-height:1.14;letter-spacing:-.025em;}}
      .pp-ra-heading p {{margin:0;color:#586b7b;font-size:14px;line-height:1.5;}}
      .pp-ra-badge {{padding:8px 11px;border-radius:999px;background:#e7f3ed;color:#238a52;
        white-space:nowrap;font-size:10px;font-weight:850;letter-spacing:.08em;}}
      .pp-ra-metrics {{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-top:20px;}}
      .pp-ra-metrics article {{padding:13px;border:1px solid #ece7de;border-radius:12px;background:#f7f4ee;}}
      .pp-ra-metrics article span {{display:block;color:#65798b;font-size:10px;
        line-height:1.35;font-weight:800;letter-spacing:.07em;}}
      .pp-ra-metrics article strong {{display:block;margin-top:7px;color:#10263d;
        font-size:27px;line-height:1;font-weight:850;}}
      @media(max-width:760px) {{.pp-ra-heading{{display:block}}.pp-ra-badge{{display:inline-block;margin-top:12px}}
        .pp-ra-metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
    </style>
    """


def _show_recognition_audit(report: RecognitionAuditReport) -> None:
    st.markdown(build_recognition_audit_html(report), unsafe_allow_html=True)

    if report.review_queue:
        st.subheader("Runs the recognition engine should review")
        st.caption(
            "These are proposed evidence checks, not changes. High-priority "
            "items have a convincing lap-pattern conflict."
        )
        queue_rows = [
            {
                "Date": entry.activity_date,
                "Activity": entry.title,
                "Current view": entry.current_label,
                "Audit view": entry.proposed_label,
                "Confidence": f"{entry.current_confidence:.0%}",
                "Priority": entry.review_priority.title(),
                "Why": entry.recommendation,
            }
            for entry in report.review_queue[:100]
        ]
        st.dataframe(
            pd.DataFrame(queue_rows),
            hide_index=True,
            width="stretch",
            height=min(470, 90 + len(queue_rows) * 35),
        )

        review_options = {
            f"{entry.activity_date} · {entry.title} · {entry.issue_key}": entry
            for entry in report.review_queue[:100]
        }
        selected_key = st.selectbox(
            "Choose a flagged activity to inspect",
            list(review_options),
            key=f"recognition_audit_review_{report.athlete_id}",
        )
        selected = review_options[selected_key]
        structure = selected.interval_evidence
        st.write(
            f"**Evidence:** {' '.join(selected.evidence)} "
            f"Recorded work: {structure.work_count} repetition(s), "
            f"{structure.credible_recovery_count} credible recovery segment(s)."
        )
        url = activity_review_url(report.athlete_id, selected.activity_id)
        st.markdown(
            f"[Open this activity and its existing coach corrections]({url})"
        )
    else:
        st.success("No unresolved classification conflicts were found for this athlete.")

    with st.expander("Suggested real-session reference set", expanded=False):
        st.caption(
            "A balanced selection of real activities for checking future recognition "
            "rules. The same selection method works for every athlete."
        )
        cases = [
            {
                "Date": entry.activity_date,
                "Activity": entry.title,
                "Expected direction": entry.proposed_label,
                "Audit status": entry.audit_status.replace("_", " ").title(),
                "Why selected": entry.issue_key or entry.proposed_session_type,
            }
            for entry in report.reference_cases
        ]
        if cases:
            st.dataframe(pd.DataFrame(cases), hide_index=True, width="stretch")
        else:
            st.info("No running activities are available for a reference set yet.")


def show_diagnostics_page():
    st.title("Session Recognition & Evidence Audit")
    st.caption(
        "Inspect how every athlete's real activities are recognised, identify "
        "conflicting evidence, and review the original laps safely."
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

    with st.spinner("Auditing this athlete's real running history..."):
        audit = _load_recognition_audit(athlete["id"], data_version)
    _show_recognition_audit(audit)

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
        _load_recognition_audit.clear()
        st.rerun()
