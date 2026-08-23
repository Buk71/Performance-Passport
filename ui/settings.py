import datetime

import streamlit as st

from core.database import (
    get_athletes_with_effective_thresholds,
    save_threshold_override,
    clear_threshold_override,
)


def athlete_full_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()


def _date_value(value):
    if not value:
        return datetime.date.today()

    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return datetime.date.today()


def show_settings_page():
    st.title("Settings")
    st.write(
        "Manage physiological thresholds and choose whether Performance "
        "Passport uses profile, estimated or verified test values."
    )

    athletes = get_athletes_with_effective_thresholds()

    if not athletes:
        st.info("Add an athlete before configuring thresholds.")
        return

    names = [
        athlete_full_name(row["first_name"], row["last_name"])
        for row in athletes
    ]
    selected_name = st.selectbox("Athlete", names)
    athlete = athletes[names.index(selected_name)]

    st.subheader("Physiological thresholds")
    st.caption(
        "Manual values can come from a laboratory test, coach assessment or "
        "reliable field test. Automatic estimates remain visible and are used "
        "only when no profile or verified value is available."
    )

    estimated = st.columns(3)
    estimated[0].metric(
        "Estimated LT1",
        f"{athlete['estimated_lt1_hr']} bpm"
        if athlete["estimated_lt1_hr"] else "Building evidence",
    )
    estimated[1].metric(
        "Estimated LT2",
        f"{athlete['estimated_lt2_hr']} bpm"
        if athlete["estimated_lt2_hr"] else "Building evidence",
    )
    estimated[2].metric(
        "Estimate confidence",
        athlete["estimate_confidence"],
        f"{athlete['estimate_sample_size']:,} reliable runs",
    )

    calculated = st.columns(3)
    calculated[0].metric(
        "Profile / entered LT1",
        f"{athlete['calculated_lt1_hr']} bpm"
        if athlete["calculated_lt1_hr"]
        else "Not set",
    )
    calculated[1].metric(
        "Profile / entered LT2",
        f"{athlete['calculated_lt2_hr']} bpm"
        if athlete["calculated_lt2_hr"]
        else "Not set",
    )
    calculated[2].metric(
        "Profile / entered Max HR",
        f"{athlete['calculated_max_hr']} bpm"
        if athlete["calculated_max_hr"]
        else "Not set",
    )

    source_options = [
        "Use profile or automatic estimate",
        "Use verified test values",
    ]
    current_manual = athlete["override_enabled"]
    selected_source = st.radio(
        "Active source",
        source_options,
        index=1 if current_manual else 0,
        horizontal=True,
    )

    if selected_source == "Use verified test values":
        with st.form(f"threshold_override_{athlete['id']}"):
            cols = st.columns(3)
            manual_lt1 = cols[0].number_input(
                "Manual LT1 HR",
                min_value=0,
                max_value=250,
                value=int(
                    athlete["manual_lt1_hr"]
                    or athlete["calculated_lt1_hr"]
                    or athlete["estimated_lt1_hr"]
                    or 0
                ),
            )
            manual_lt2 = cols[1].number_input(
                "Manual LT2 HR",
                min_value=0,
                max_value=250,
                value=int(
                    athlete["manual_lt2_hr"]
                    or athlete["calculated_lt2_hr"]
                    or athlete["estimated_lt2_hr"]
                    or 0
                ),
            )
            manual_max = cols[2].number_input(
                "Manual Max HR",
                min_value=0,
                max_value=250,
                value=int(
                    athlete["manual_max_hr"]
                    or athlete["calculated_max_hr"]
                    or athlete["estimated_max_hr"]
                    or 0
                ),
            )

            source = st.selectbox(
                "Evidence source",
                [
                    "Laboratory test",
                    "Coach assessment",
                    "Field test",
                    "Known personal value",
                    "Other",
                ],
                index=(
                    [
                        "Laboratory test",
                        "Coach assessment",
                        "Field test",
                        "Known personal value",
                        "Other",
                    ].index(athlete["override_source"])
                    if athlete["override_source"] in {
                        "Laboratory test",
                        "Coach assessment",
                        "Field test",
                        "Known personal value",
                        "Other",
                    }
                    else 0
                ),
            )
            tested_at = st.date_input(
                "Test or assessment date",
                value=_date_value(athlete["tested_at"]),
            )
            notes = st.text_area(
                "Notes",
                value=athlete["override_notes"] or "",
                placeholder="For example: Leeds Beckett lab assessment.",
            )

            submitted = st.form_submit_button(
                "Save and use manual thresholds"
            )

        if submitted:
            if manual_lt1 and manual_lt2 and manual_lt1 >= manual_lt2:
                st.error("LT1 must be lower than LT2.")
            elif manual_lt2 and manual_max and manual_lt2 >= manual_max:
                st.error("LT2 must be lower than Max HR.")
            else:
                save_threshold_override(
                    athlete_id=athlete["id"],
                    lt1_hr=manual_lt1 or None,
                    lt2_hr=manual_lt2 or None,
                    max_hr=manual_max or None,
                    source=source,
                    tested_at=str(tested_at),
                    notes=notes,
                )
                st.success("Manual thresholds saved and activated.")
                st.rerun()
    else:
        if current_manual:
            if st.button("Clear tested override"):
                clear_threshold_override(athlete["id"])
                st.success("Profile or automatic values restored.")
                st.rerun()

    st.divider()
    st.subheader("Current values used by the coaches")

    effective = st.columns(3)
    effective[0].metric(
        "Active LT1",
        f"{athlete['effective_lt1_hr']} bpm"
        if athlete["effective_lt1_hr"]
        else "Not set",
    )
    effective[1].metric(
        "Active LT2",
        f"{athlete['effective_lt2_hr']} bpm"
        if athlete["effective_lt2_hr"]
        else "Not set",
    )
    effective[2].metric(
        "Active Max HR",
        f"{athlete['effective_max_hr']} bpm"
        if athlete["effective_max_hr"]
        else "Not set",
    )

    st.caption(
        f"Source: {athlete['effective_source']}. "
        "Easy Run Coach and future coaching engines use these active values."
    )
