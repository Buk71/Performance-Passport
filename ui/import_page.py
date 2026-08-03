import json
import sqlite3

import pandas as pd
import streamlit as st

from core.database import get_connection


def athlete_full_name(first_name, last_name):
    """Return a clean athlete display name."""
    return f"{first_name or ''} {last_name or ''}".strip()


def get_athletes():
    """Return all athletes available for import."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, first_name, last_name
        FROM athletes
        ORDER BY first_name, last_name
        """
    )

    athletes = cursor.fetchall()
    conn.close()

    return athletes


def get_athlete_activity_count(athlete_id):
    """Return the number of activities assigned to one athlete."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM activities
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )

    count = cursor.fetchone()[0]
    conn.close()

    return count


def get_database_activity_count():
    """Return the total number of activities in the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM activities")
    count = cursor.fetchone()[0]

    conn.close()
    return count


def initialise_import_athlete(athlete_names):
    """Use the shared athlete selection when it is valid."""
    selected_name = st.session_state.get("selected_athlete_name")

    if selected_name not in athlete_names:
        selected_name = athlete_names[0]
        st.session_state.selected_athlete_name = selected_name

    st.session_state.import_athlete_widget = selected_name


def update_import_athlete():
    """Persist the athlete chosen on the Import page."""
    st.session_state.selected_athlete_name = (
        st.session_state.import_athlete_widget
    )


def _value(row, column):
    """Safely get a value from a dataframe row."""
    if column not in row:
        return None

    value = row[column]

    if pd.isna(value):
        return None

    return value


def _clean_value(value):
    """Convert pandas/numpy values into SQLite-friendly values."""
    if value is None:
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def import_runalyze_dataframe(
    df,
    athlete_id,
    athlete_name,
):
    """Import a Runalyze dataframe for one specific athlete."""

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

            values = (
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
                values,
            )

            imported += 1

        except sqlite3.IntegrityError:
            duplicates += 1

        except Exception as error:
            errors += 1

            st.error(
                f"""
Activity ID: {source_activity_id or "Unknown"}

Error: {error}
"""
            )

            break

    conn.commit()
    conn.close()

    return imported, duplicates, errors


def show_import_page():
    st.title("📥 Import")

    athletes = get_athletes()

    if not athletes:
        st.warning("No athletes exist yet. Add an athlete before importing.")
        return

    athlete_options = {
        athlete_full_name(first_name, last_name): {
            "id": athlete_id,
            "name": athlete_full_name(first_name, last_name),
        }
        for athlete_id, first_name, last_name in athletes
    }

    athlete_names = list(athlete_options.keys())
    initialise_import_athlete(athlete_names)

    st.selectbox(
        "Import destination",
        athlete_names,
        key="import_athlete_widget",
        on_change=update_import_athlete,
    )

    selected_name = st.session_state.selected_athlete_name
    selected_athlete = athlete_options.get(selected_name)

    if selected_athlete is None:
        st.error("The selected athlete could not be found.")
        return

    athlete_id = selected_athlete["id"]
    athlete_name = selected_athlete["name"]

    athlete_count = get_athlete_activity_count(athlete_id)
    database_count = get_database_activity_count()

    st.success(f"Importing into: **{athlete_name}**")

    count_col1, count_col2 = st.columns(2)

    count_col1.metric(
        f"{athlete_name} activities",
        f"{athlete_count:,}",
    )

    count_col2.metric(
        "Total database activities",
        f"{database_count:,}",
    )

    st.caption(
        "Activities imported here will be assigned only to the athlete "
        "shown above."
    )

    import_type = st.radio(
        "Import type",
        ["Runalyze CSV", "FIT file"],
    )

    if import_type == "Runalyze CSV":
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

        st.success(
            f"Runalyze file loaded successfully: {len(df):,} activities"
        )

        sport_column = "sportid" if "sportid" in df.columns else None

        if sport_column:
            sports = sorted(
                df[sport_column]
                .dropna()
                .astype(str)
                .unique()
            )

            selected_sports = st.multiselect(
                "Activity types / sport IDs",
                sports,
                default=sports,
            )

            df = df[
                df[sport_column]
                .astype(str)
                .isin(selected_sports)
            ]
        else:
            st.warning("No activity type column was found.")

        date_column = "time" if "time" in df.columns else None

        if date_column:
            df = df.copy()

            df["activity_date"] = pd.to_datetime(
                df[date_column],
                unit="s",
                errors="coerce",
            )

            df = df.dropna(subset=["activity_date"])

            if df.empty:
                st.warning(
                    "No activities remain after processing the date column."
                )
                return

            min_date = df["activity_date"].min().date()
            max_date = df["activity_date"].max().date()

            date_range = st.date_input(
                "Date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )

            if len(date_range) == 2:
                start_date, end_date = date_range

                df = df[
                    (df["activity_date"].dt.date >= start_date)
                    & (df["activity_date"].dt.date <= end_date)
                ]
        else:
            st.warning("No date column was found.")

        st.divider()

        st.metric("Activities ready to import", len(df))

        st.info(
            f"These activities will be imported into "
            f"**{athlete_name}**."
        )

        st.dataframe(
            df.head(20),
            width="stretch",
        )

        confirmation = st.checkbox(
            f"I confirm these activities belong to {athlete_name}.",
            key="confirm_import_athlete",
        )

        if st.button(
            "Import Activities",
            type="primary",
            disabled=not confirmation or df.empty,
        ):
            with st.spinner(
                f"Importing activities into {athlete_name}..."
            ):
                imported, duplicates, errors = (
                    import_runalyze_dataframe(
                        df=df,
                        athlete_id=athlete_id,
                        athlete_name=athlete_name,
                    )
                )

            if errors:
                st.warning(
                    f"Import completed with {errors} error(s)."
                )
            else:
                st.success(
                    f"Import complete for {athlete_name}."
                )

            updated_athlete_count = get_athlete_activity_count(
                athlete_id
            )
            updated_database_count = get_database_activity_count()

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Imported", imported)
            col2.metric("Duplicates", duplicates)
            col3.metric("Errors", errors)
            col4.metric(
                f"{athlete_name} total",
                updated_athlete_count,
            )

            st.caption(
                f"Total activities across all athletes: "
                f"{updated_database_count:,}"
            )

    else:
        st.info(
            "FIT file import will come after the Runalyze CSV pipeline."
        )