import json
import sqlite3

import pandas as pd
import streamlit as st

from core.database import get_activity_count, get_connection


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


def import_runalyze_dataframe(df, athlete_name):
    """Import a Runalyze dataframe into the activities table."""

    conn = get_connection()
    cursor = conn.cursor()

    imported = 0
    duplicates = 0
    errors = 0

    for _, row in df.iterrows():
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
                row.astype(object).where(pd.notnull(row), None).to_dict(),
                default=str,
            )

            values = (
                athlete_name,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

            imported += 1

        except sqlite3.IntegrityError:
            duplicates += 1

        except Exception as e:
            errors += 1

            st.error(
                f"""
Activity ID:
{source_activity_id}

Error:
{e}
"""
            )

            break

    conn.commit()
    conn.close()

    return imported, duplicates, errors


def show_import_page():
    st.title("📥 Import")

    st.write("Import activity data into Performance Passport.")

    st.info(f"Database currently contains **{get_activity_count():,}** activities.")

    import_type = st.radio(
        "Import type",
        ["Runalyze CSV", "FIT file"],
    )

    if import_type == "Runalyze CSV":
        uploaded_file = st.file_uploader(
            "Upload Runalyze CSV export",
            type=["csv"],
        )

        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)

            st.success(f"Runalyze file loaded successfully: {len(df):,} activities")

            athlete = st.selectbox(
                "Athlete",
                ["Richard", "Jo"],
            )

            sport_column = "sportid" if "sportid" in df.columns else None

            if sport_column:
                sports = sorted(df[sport_column].dropna().astype(str).unique())

                selected_sports = st.multiselect(
                    "Activity types / sport IDs",
                    sports,
                    default=sports,
                )

                df = df[df[sport_column].astype(str).isin(selected_sports)]
            else:
                st.warning("No activity type column found yet.")

            date_column = "time" if "time" in df.columns else None

            if date_column:
                df = df.copy()

                df["activity_date"] = pd.to_datetime(
                    df[date_column],
                    unit="s",
                    errors="coerce",
                )

                df = df.dropna(subset=["activity_date"])

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
                st.warning("No date column found yet.")

            st.divider()

            st.metric("Activities ready to import", len(df))

            st.write(f"Selected athlete: **{athlete}**")

            st.dataframe(
                df.head(20),
                width="stretch",
            )

            if st.button("Import Activities", type="primary"):
                with st.spinner("Importing activities into database..."):
                    imported, duplicates, errors = import_runalyze_dataframe(
                        df,
                        athlete,
                    )

                st.success("Import complete")

                col1, col2, col3, col4 = st.columns(4)

                col1.metric("Imported", imported)
                col2.metric("Duplicates", duplicates)
                col3.metric("Errors", errors)
                col4.metric("Database total", get_activity_count())

    else:
        st.info("FIT file import will come after the Runalyze CSV pipeline.")