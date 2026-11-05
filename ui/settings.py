import datetime

import streamlit as st

from ui.runner_onboarding import show_runner_profile_editor
from ui.athlete_selection import SESSION_ID_KEY, SESSION_NAME_KEY

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
    # Streamlit expanders inherit a dark theme treatment elsewhere in the app.
    # Keep their headings legible and visibly interactive on this settings page.
    st.markdown("""<style>
    div[data-testid="stExpander"] details > summary {
        background: #F4F0E9 !important;
        border: 1px solid #D8D2C8 !important;
        border-radius: 10px !important;
        cursor: pointer !important;
        padding: 12px 16px !important;
    }
    div[data-testid="stExpander"] details > summary:hover {
        background: #EAE3D9 !important;
        border-color: #EF6A3A !important;
    }
    div[data-testid="stExpander"] details > summary *,
    div[data-testid="stExpander"] details > summary p,
    div[data-testid="stExpander"] details > summary svg {
        color: #1D2B38 !important;
        fill: #1D2B38 !important;
        -webkit-text-fill-color: #1D2B38 !important;
        opacity: 1 !important;
        font-weight: 650 !important;
    }
    div[data-testid="stExpander"] details[open] > summary {
        border-bottom: 2px solid #EF6A3A !important;
    }
    </style>""", unsafe_allow_html=True)
    st.title("Settings")
    st.write(
        "Review your running profile and see exactly which heart-rate values your coaches use."
    )

    athletes = get_athletes_with_effective_thresholds()

    if not athletes:
        st.info("Add an athlete before configuring thresholds.")
        return

    names = [
        athlete_full_name(row["first_name"], row["last_name"])
        for row in athletes
    ]
    ids = [int(row["id"]) for row in athletes]
    active_id = st.session_state.get(SESSION_ID_KEY)
    if active_id not in ids:
        active_id = ids[0]
    # Settings follows the canonical athlete selection, rather than defaulting
    # independently to the first athlete. The selector can still switch athletes.
    selected_id = st.selectbox(
        "Athlete", ids, index=ids.index(active_id),
        format_func=lambda athlete_id: names[ids.index(athlete_id)],
    )
    # On each rerun, reconcile the settings widget with the canonical selection.
    # Streamlit persists keyed widgets, so a callback is needed for deliberate changes.
    athlete = athletes[ids.index(selected_id)]
    st.session_state[SESSION_ID_KEY] = int(selected_id)
    st.session_state[SESSION_NAME_KEY] = names[ids.index(selected_id)]
    st.caption(f"You are editing **{names[ids.index(selected_id)]}**. Changes affect only this athlete.")

    with st.expander("My running profile — experience and availability", expanded=True):
        show_runner_profile_editor(int(athlete["id"]))

    st.subheader("Heart-rate thresholds")
    st.write("**These are the values your coaches currently use.** The source below each value tells you why it is active.")
    from ui.threshold_display import threshold_source
    active = st.columns(3)
    for col, label, field in zip(active, ("LT1", "LT2", "Maximum HR"), ("lt1", "lt2", "max")):
        value = athlete[f"effective_{field}_hr"]
        col.metric(label, f"{value} bpm" if value else "Not set")
        col.caption(threshold_source(athlete, field))

    if not athlete["override_enabled"] and any(athlete[f"calculated_{field}_hr"] for field in ("lt1", "lt2", "max")):
        st.info(
            "Stored profile values are currently taking priority where available. "
            "If these originally came from a threshold test, you can record that source below "
            "without changing the numbers. The app cannot infer the original test source."
        )

    with st.expander("Compare with automatic estimates", expanded=False):
        st.write("Automatic estimates are comparisons, **not necessarily the values being used**.")
        estimated = st.columns(3)
        for col, label, field in zip(estimated, ("Estimated LT1", "Estimated LT2", "Estimated Max HR"), ("lt1", "lt2", "max")):
            value = athlete[f"estimated_{field}_hr"]
            col.metric(label, f"{value} bpm" if value else "Building evidence")
        st.caption(f"Estimate confidence: {athlete['estimate_confidence']} · {athlete['estimate_sample_size']:,} reliable runs")

    with st.expander("Record test source or change active thresholds", expanded=False):
        st.write(
            "Your current values will be pre-filled. Saving explicitly activates the supplied "
            "test values and records their source; it does not independently verify them."
        )
        with st.form(f"threshold_evidence_{athlete['id']}"):
            cols = st.columns(3)
            values = []
            for col, label, field in zip(cols, ("LT1 (bpm)", "LT2 (bpm)", "Maximum HR (bpm)"), ("lt1", "lt2", "max")):
                values.append(col.number_input(
                    label, min_value=0, max_value=250,
                    value=int(athlete[f"effective_{field}_hr"] or 0),
                    help="Leave at zero if this threshold is unknown.",
                ))
            sources = ["Laboratory test", "Coach assessment", "Field test", "Known personal value", "Other"]
            recorded = athlete["override_source"]
            source = st.selectbox("Where did these values come from?", sources,
                                  index=sources.index(recorded) if recorded in sources else 0)
            date_text = st.text_input(
                "Test date (optional, YYYY-MM-DD)",
                value=str(athlete["tested_at"] or ""),
                placeholder="Leave blank if unknown",
            )
            notes = st.text_area("Notes (optional)", value=athlete["override_notes"] or "")
            submitted = st.form_submit_button("Save source and use these values", type="primary")
        if submitted:
            lt1, lt2, max_hr = values
            if lt1 and lt2 and lt1 >= lt2:
                st.error("LT1 must be lower than LT2.")
            elif lt2 and max_hr and lt2 >= max_hr:
                st.error("LT2 must be lower than maximum HR.")
            elif date_text and not _valid_iso_date(date_text):
                st.error("Enter the date as YYYY-MM-DD, or leave it blank.")
            else:
                save_threshold_override(
                    athlete_id=athlete["id"], lt1_hr=lt1 or None,
                    lt2_hr=lt2 or None, max_hr=max_hr or None,
                    source=source, tested_at=date_text or None, notes=notes,
                )
                st.success("Test source saved. The displayed values remain unchanged if you kept the defaults.")
                st.rerun()

        if athlete["override_enabled"]:
            st.caption("A manually supplied test record is active. You can return to stored profile / automatic fallback values.")
            if st.button("Stop using manually supplied test values", key=f"clear_threshold_{athlete['id']}"):
                clear_threshold_override(athlete["id"])
                st.rerun()


def _valid_iso_date(value):
    try:
        return datetime.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False
