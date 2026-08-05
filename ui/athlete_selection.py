"""
Shared athlete selection for all athlete-facing pages.

The selected athlete is stored once in Streamlit session state so Coach,
Hall of Fame and future pages remain synchronised.
"""

from __future__ import annotations

import streamlit as st

from core.database import get_connection


SESSION_NAME_KEY = "selected_athlete_name"
SESSION_ID_KEY = "selected_athlete_id"


def get_athletes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, first_name, last_name
        FROM athletes
        ORDER BY first_name, last_name, id
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def athlete_name(row):
    return f"{row[1] or ''} {row[2] or ''}".strip()


def initialise_selected_athlete(athletes):
    if not athletes:
        return None

    names = [athlete_name(row) for row in athletes]
    ids_by_name = {
        athlete_name(row): row[0]
        for row in athletes
    }

    selected_name = st.session_state.get(SESSION_NAME_KEY)
    selected_id = st.session_state.get(SESSION_ID_KEY)

    if (
        selected_name not in ids_by_name
        or ids_by_name.get(selected_name) != selected_id
    ):
        selected_name = names[0]
        selected_id = ids_by_name[selected_name]

    st.session_state[SESSION_NAME_KEY] = selected_name
    st.session_state[SESSION_ID_KEY] = selected_id

    return selected_id


def render_athlete_selector(
    *,
    key: str,
    label: str = "Athlete",
    label_visibility: str = "visible",
):
    athletes = get_athletes()

    if not athletes:
        return None

    initialise_selected_athlete(athletes)

    names = [athlete_name(row) for row in athletes]
    ids_by_name = {
        athlete_name(row): row[0]
        for row in athletes
    }

    current_name = st.session_state[SESSION_NAME_KEY]

    if (
        key not in st.session_state
        or st.session_state[key] not in names
    ):
        st.session_state[key] = current_name

    selected_name = st.selectbox(
        label,
        names,
        key=key,
        label_visibility=label_visibility,
    )

    selected_id = ids_by_name[selected_name]
    st.session_state[SESSION_NAME_KEY] = selected_name
    st.session_state[SESSION_ID_KEY] = selected_id

    return selected_id
