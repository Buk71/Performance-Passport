import json
import sqlite3

import pandas as pd
import streamlit as st

from core.database import (
    backfill_missing_athlete_ids,
    get_connection,
    refresh_athlete_sport_mappings,
)
from core.garmin_import import (
    discover_fit_payloads,
    import_garmin_activities,
    parse_fit_payloads,
)
from ui.athlete_selection import render_athlete_id_selector


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
                SELECT id
                FROM activities
                WHERE athlete_id = ?
                  AND source = 'runalyze_csv'
                  AND source_activity_id = ?
                LIMIT 1
                """,
                (athlete_id, source_activity_id),
            )

            if cursor.fetchone() is not None:
                duplicates += 1
                continue

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


@st.cache_data(show_spinner=False, ttl=600)
def _cached_garmin_uploads(uploads):
    discovery = discover_fit_payloads(uploads)
    parsed = parse_fit_payloads(discovery.payloads)
    return discovery, parsed


def _show_garmin_import(athlete_id, athlete_name):
    st.markdown("### Garmin activity files")
    st.write(
        "Upload individual Garmin `.fit` activities, several FIT files at "
        "once, or a Garmin export ZIP. Nested activity ZIPs are discovered "
        "automatically."
    )
    st.caption(
        "The original FIT file is retained as the source of truth. Existing "
        "Runalyze versions of the same activity are enriched rather than "
        "added for a second time."
    )

    uploaded_files = st.file_uploader(
        "Upload Garmin FIT files or export ZIPs",
        type=["fit", "zip"],
        accept_multiple_files=True,
        key="garmin_fit_uploads",
    )
    if not uploaded_files:
        st.info(
            "In Garmin Connect on the web, Export Original downloads a FIT "
            "activity. A full Garmin data export can be uploaded as ZIP "
            "files, in manageable batches if the archive is very large."
        )
        return

    uploads = tuple(
        (uploaded.name, uploaded.getvalue())
        for uploaded in uploaded_files
    )
    with st.spinner("Reading Garmin activity evidence…"):
        discovery, parsed = _cached_garmin_uploads(uploads)

    running = [activity for activity in parsed.activities if activity.is_running]
    other = [activity for activity in parsed.activities if not activity.is_running]
    dates = sorted(activity.activity_date for activity in parsed.activities)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("FIT files found", f"{len(discovery.payloads):,}")
    col2.metric("Running activities", f"{len(running):,}")
    col3.metric("Other sports", f"{len(other):,}")
    col4.metric(
        "Files needing review",
        f"{len(discovery.issues) + len(parsed.issues):,}",
    )

    if dates:
        st.success(
            f"Garmin evidence ready for {athlete_name}: "
            f"{dates[0]} to {dates[-1]}."
        )
    if discovery.repeated_files:
        st.info(
            f"{discovery.repeated_files:,} repeated file(s) inside the "
            "selected uploads were ignored before import."
        )

    issues = (*discovery.issues, *parsed.issues)
    if issues:
        with st.expander(f"Files needing review ({len(issues):,})"):
            for issue in issues:
                st.write(f"• {issue}")

    if not parsed.activities:
        st.error("No valid Garmin activity FIT files were available to import.")
        return

    running_only = st.checkbox(
        "Import running activities only",
        value=True,
        help=(
            "Recommended for Performance Passport. Other Garmin sports remain "
            "outside this import unless you deliberately include them."
        ),
    )
    ready = running if running_only else list(parsed.activities)
    st.metric("Activities ready to import", f"{len(ready):,}")
    st.info(f"These activities will be assigned only to **{athlete_name}**.")

    confirmation = st.checkbox(
        f"I confirm these Garmin activities belong to {athlete_name}.",
        key="garmin_import_confirmation",
    )
    if st.button(
        "Import Garmin Activities",
        type="primary",
        disabled=not confirmation or not ready,
        use_container_width=True,
    ):
        with st.spinner(f"Importing Garmin evidence into {athlete_name}…"):
            result = import_garmin_activities(
                parsed.activities,
                athlete_id=athlete_id,
                athlete_name=athlete_name,
                running_only=running_only,
            )
        st.cache_data.clear()
        st.success(f"Garmin import complete for {athlete_name}.")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("New", result.imported)
        c2.metric("Enriched", result.enriched)
        c3.metric("Duplicates", result.duplicates)
        c4.metric("Other sports skipped", result.skipped_non_running)
        c5.metric(
            f"{athlete_name} total",
            get_athlete_activity_count(athlete_id),
        )
        if result.errors:
            with st.expander(f"Import errors ({len(result.errors):,})"):
                for error in result.errors:
                    st.write(f"• {error}")


def show_import_page():
    st.title("📥 Import")

    athletes = get_athletes()

    if not athletes:
        st.warning("Add an athlete before importing.")
        return

    athlete_id = render_athlete_id_selector(label="Import destination")
    if athlete_id is None:
        st.warning("Add an athlete before importing.")
        return
    athlete_names = {
        int(row[0]): athlete_full_name(row[1], row[2])
        for row in athletes
    }
    athlete_name = athlete_names[athlete_id]

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
        ["Runalyze CSV", "Garmin FIT / ZIP"],
        horizontal=True,
    )

    if import_type == "Garmin FIT / ZIP":
        _show_garmin_import(athlete_id, athlete_name)
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
