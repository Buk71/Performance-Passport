import json
import sqlite3

import pandas as pd
import streamlit as st

from core.database import (
    backfill_missing_athlete_ids,
    get_connection,
    refresh_athlete_sport_mappings,
)


def athlete_full_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()


def get_athletes():
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
    return rows


def get_athlete_activity_count(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM activities WHERE athlete_id = ?",
        (athlete_id,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_database_activity_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activities")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def _value(row, column):
    if column not in row:
        return None
    value = row[column]
    if pd.isna(value):
        return None
    return value


def _clean_value(value):
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def import_runalyze_dataframe(df, athlete_id, athlete_name):
    conn = get_connection()
    cursor = conn.cursor()

    imported = 0
    duplicates = 0
    errors = 0

    for _, row in df.iterrows():
        source_activity_id = None

        try:
            source_activity_id = str(_value(row, "id"))

            if not source_activity_id or source_activity_id == "None":
                errors += 1
                continue

            activity_datetime = _value(row, "activity_date")
            activity_datetime_text = (
                activity_datetime.isoformat()
                if activity_datetime is not None
                else None
            )
            activity_date_text = (
                activity_datetime.date().isoformat()
                if activity_datetime is not None
                else None
            )

            raw_json = json.dumps(
                row.astype(object)
                .where(pd.notnull(row), None)
                .to_dict(),
                default=str,
            )

            cursor.execute(
                """
                INSERT INTO activities (
                    athlete_name,
                    athlete_id,
                    source,
                    source_activity_id,
                    activity_hash,
                    activity_datetime,
                    activity_date,
                    title,
                    sport_id,
                    type_id,
                    distance_m,
                    moving_time_s,
                    elapsed_time_s,
                    elevation_up_m,
                    elevation_down_m,
                    avg_hr,
                    max_hr,
                    avg_power,
                    cadence,
                    calories,
                    temperature_c,
                    humidity,
                    wind_speed,
                    route_name,
                    equipment_ids,
                    original_file,
                    raw_json
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    athlete_name,
                    athlete_id,
                    "runalyze_csv",
                    source_activity_id,
                    _clean_value(_value(row, "hash")),
                    activity_datetime_text,
                    activity_date_text,
                    _clean_value(_value(row, "title")),
                    _clean_value(_value(row, "sportid")),
                    _clean_value(_value(row, "typeid")),
                    _clean_value(_value(row, "distance")),
                    _clean_value(_value(row, "s")),
                    _clean_value(_value(row, "elapsedTime")),
                    _clean_value(_value(row, "elevationUp")),
                    _clean_value(_value(row, "elevationDown")),
                    _clean_value(_value(row, "pulseAvg")),
                    _clean_value(_value(row, "pulseMax")),
                    _clean_value(_value(row, "power")),
                    _clean_value(_value(row, "cadence")),
                    _clean_value(_value(row, "kcal")),
                    _clean_value(_value(row, "temperature")),
                    _clean_value(_value(row, "humidity")),
                    _clean_value(_value(row, "windSpeed")),
                    _clean_value(_value(row, "routeName")),
                    _clean_value(_value(row, "equipmentIds")),
                    _clean_value(_value(row, "original_file")),
                    raw_json,
                ),
            )
            imported += 1

        except sqlite3.IntegrityError:
            duplicates += 1
        except Exception as error:
            errors += 1
            st.error(
                f"Activity ID: {source_activity_id or 'Unknown'}\n\n"
                f"Error: {error}"
            )
            break

    backfill_missing_athlete_ids(cursor)

    conn.commit()
    conn.close()

    refresh_athlete_sport_mappings()
    st.cache_data.clear()

    return imported, duplicates, errors


def show_import_page():
    st.title("📥 Import")

    athletes = get_athletes()

    if not athletes:
        st.warning("Add an athlete before importing.")
        return

    options = {
        athlete_full_name(first_name, last_name): athlete_id
        for athlete_id, first_name, last_name in athletes
    }

    names = list(options.keys())
    selected = st.session_state.get("selected_athlete_name", names[0])

    if selected not in names:
        selected = names[0]

    athlete_name = st.selectbox(
        "Import destination",
        names,
        index=names.index(selected),
    )
    st.session_state.selected_athlete_name = athlete_name

    athlete_id = options[athlete_name]

    st.success(f"Importing into: **{athlete_name}**")

    col1, col2 = st.columns(2)
    col1.metric(
        f"{athlete_name} activities",
        f"{get_athlete_activity_count(athlete_id):,}",
    )
    col2.metric(
        "Total database activities",
        f"{get_database_activity_count():,}",
    )

    import_type = st.radio(
        "Import type",
        ["Runalyze CSV", "FIT file"],
    )

    if import_type != "Runalyze CSV":
        st.info("FIT import will be added later.")
        return

    uploaded_file = st.file_uploader(
        "Upload Runalyze CSV export",
        type=["csv"],
    )

    if uploaded_file is None:
        return

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as error:
        st.error(f"The CSV could not be read: {error}")
        return

    st.success(f"File loaded: {len(df):,} activities")

    if "sportid" in df.columns:
        sports = sorted(df["sportid"].dropna().astype(str).unique())
        selected_sports = st.multiselect(
            "Activity types / sport IDs",
            sports,
            default=sports,
        )
        df = df[df["sportid"].astype(str).isin(selected_sports)]

    if "time" in df.columns:
        df = df.copy()
        df["activity_date"] = pd.to_datetime(
            df["time"],
            unit="s",
            errors="coerce",
        )
        df = df.dropna(subset=["activity_date"])

    st.metric("Activities ready to import", len(df))
    st.info(f"These activities will be assigned to **{athlete_name}**.")

    confirmation = st.checkbox(
        f"I confirm these activities belong to {athlete_name}."
    )

    if st.button(
        "Import Activities",
        type="primary",
        disabled=not confirmation or df.empty,
    ):
        with st.spinner(f"Importing into {athlete_name}..."):
            imported, duplicates, errors = import_runalyze_dataframe(
                df,
                athlete_id,
                athlete_name,
            )

        st.success(f"Import complete for {athlete_name}.")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Imported", imported)
        c2.metric("Duplicates", duplicates)
        c3.metric("Errors", errors)
        c4.metric(
            f"{athlete_name} total",
            get_athlete_activity_count(athlete_id),
        )
