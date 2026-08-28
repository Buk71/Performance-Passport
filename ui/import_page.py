import datetime
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
from core.garmin_connect import (
    GarminConnectPrototypeError,
    begin_login,
    complete_mfa,
    connect_with_saved_tokens,
    dependency_available,
    download_original_activities,
    fetch_garmin_preview,
    has_saved_connection,
)
from core.runalyze_health import (
    GARMIN_CONNECT_HEALTH_SOURCE,
    get_athlete_health_count,
    import_health_records,
    import_runalyze_health_records,
    parse_runalyze_health_rows,
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


def _garmin_state_key(label, athlete_id):
    return f"pp_garmin_connect_{label}_{int(athlete_id)}"


def _safe_garmin_error(error):
    message = " ".join(str(error or "Garmin Connect request failed.").split())
    return message[:500]


def _store_garmin_login(result, athlete_id):
    st.session_state[_garmin_state_key("client", athlete_id)] = result.client
    if result.account_name:
        st.session_state[_garmin_state_key("account", athlete_id)] = (
            result.account_name
        )


def _show_garmin_connect(athlete_id, athlete_name):
    st.markdown("### Experimental Garmin Connect")
    st.write(
        "Preview running activities and recent recovery data, then confirm the "
        "destination athlete before anything is imported."
    )
    st.warning(
        "Private prototype: this uses the unofficial python-garminconnect "
        "connector, not Garmin's commercial API. It makes read-only data calls."
    )
    st.caption(
        "Your Garmin password is used only for the sign-in request and is not "
        "stored by Performance Passport. Persistent session tokens are kept "
        "locally for this athlete in `.garmin_tokens/`, which is excluded from Git."
    )
    if not dependency_available():
        st.error(
            "Garmin Connect support is not installed. Run "
            "`python -m pip install -r requirements.txt`, restart the app and "
            "return to this page."
        )
        return

    client_key = _garmin_state_key("client", athlete_id)
    account_key = _garmin_state_key("account", athlete_id)
    mfa_key = _garmin_state_key("mfa", athlete_id)
    preview_key = _garmin_state_key("preview", athlete_id)

    if st.session_state.get(mfa_key) is not None:
        st.info("Garmin requires a verification code to finish this sign-in.")
        with st.form(_garmin_state_key("mfa_form", athlete_id), clear_on_submit=True):
            code = st.text_input("Garmin verification code", type="password")
            verify = st.form_submit_button("Verify Garmin sign-in", type="primary")
        if verify:
            try:
                result = complete_mfa(
                    st.session_state[mfa_key], code, athlete_id=athlete_id
                )
            except GarminConnectPrototypeError as error:
                st.error(_safe_garmin_error(error))
            else:
                _store_garmin_login(result, athlete_id)
                st.session_state.pop(mfa_key, None)
                st.rerun()
        return

    client = st.session_state.get(client_key)
    if client is None and has_saved_connection(athlete_id):
        if st.button(
            f"Use saved Garmin connection for {athlete_name}",
            use_container_width=True,
        ):
            try:
                result = connect_with_saved_tokens(athlete_id=athlete_id)
            except GarminConnectPrototypeError as error:
                st.error(_safe_garmin_error(error))
            else:
                _store_garmin_login(result, athlete_id)
                st.rerun()

    client = st.session_state.get(client_key)
    if client is None:
        with st.form(_garmin_state_key("login_form", athlete_id), clear_on_submit=True):
            email = st.text_input("Garmin email")
            password = st.text_input("Garmin password", type="password")
            connect = st.form_submit_button("Connect read-only", type="primary")
        if connect:
            try:
                result = begin_login(email, password, athlete_id=athlete_id)
            except GarminConnectPrototypeError as error:
                st.error(_safe_garmin_error(error))
            else:
                if result.needs_mfa:
                    st.session_state[mfa_key] = result.client
                else:
                    _store_garmin_login(result, athlete_id)
                st.rerun()
        return

    account_name = st.session_state.get(account_key, "Garmin account")
    c1, c2 = st.columns(2)
    c1.success(f"Connected read-only: **{account_name}**")
    c2.info(f"Selected destination: **{athlete_name}**")

    history_days = st.selectbox(
        "Running activity history to preview",
        options=(14, 30, 90, 365),
        index=1,
        format_func=lambda days: f"Last {days} days",
    )
    if st.button("Preview Garmin data", type="primary", use_container_width=True):
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=int(history_days) - 1)
        try:
            with st.spinner("Reading Garmin activities and recovery data…"):
                preview = fetch_garmin_preview(
                    client,
                    athlete_id=athlete_id,
                    start_date=start_date,
                    end_date=end_date,
                )
        except GarminConnectPrototypeError as error:
            st.error(_safe_garmin_error(error))
        else:
            st.session_state[preview_key] = preview

    preview = st.session_state.get(preview_key)
    if preview is None:
        st.info(
            "Preview first. Performance Passport will not download or import "
            "activity files until you confirm the account and athlete."
        )
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runs found", len(preview.activities))
    c2.metric("New runs", len(preview.new_activities))
    c3.metric(
        "Already represented",
        len(preview.activities) - len(preview.new_activities),
    )
    c4.metric("Recovery days", len(preview.health_records))

    if preview.activities:
        table = pd.DataFrame(
            {
                "Date": [item.activity_date for item in preview.activities[:50]],
                "Run": [item.title for item in preview.activities[:50]],
                "Distance (km)": [
                    round(item.distance_m / 1000.0, 2)
                    if item.distance_m is not None
                    else None
                    for item in preview.activities[:50]
                ],
                "Time (min)": [
                    round(item.duration_s / 60.0, 1)
                    if item.duration_s is not None
                    else None
                    for item in preview.activities[:50]
                ],
                "Status": [
                    "Already represented" if item.already_imported else "New"
                    for item in preview.activities[:50]
                ],
            }
        )
        st.dataframe(table, hide_index=True, use_container_width=True)
    if preview.issues:
        with st.expander(f"Preview notes ({len(preview.issues):,})"):
            for issue in preview.issues:
                st.write(f"• {_safe_garmin_error(issue)}")

    confirmation = st.checkbox(
        f"I confirm Garmin account {account_name} belongs to {athlete_name} "
        "and this preview should be imported only to this athlete.",
        key=_garmin_state_key("confirmation", athlete_id),
    )
    has_importable_data = bool(preview.new_activities or preview.health_records)
    if st.button(
        f"Import preview into {athlete_name}",
        type="primary",
        disabled=not confirmation or not has_importable_data,
        use_container_width=True,
    ):
        with st.spinner(f"Importing confirmed Garmin data into {athlete_name}…"):
            downloaded = download_original_activities(
                client, preview.new_activities
            )
            if downloaded.uploads:
                discovery = discover_fit_payloads(downloaded.uploads)
                parsed = parse_fit_payloads(discovery.payloads)
                activity_result = import_garmin_activities(
                    parsed.activities,
                    athlete_id=athlete_id,
                    athlete_name=athlete_name,
                    running_only=True,
                )
                activity_issues = (
                    *downloaded.issues,
                    *discovery.issues,
                    *parsed.issues,
                    *activity_result.errors,
                )
            else:
                activity_result = None
                activity_issues = downloaded.issues
            health_result = import_health_records(
                preview.health_records,
                athlete_id=athlete_id,
                source=GARMIN_CONNECT_HEALTH_SOURCE,
            )
        st.cache_data.clear()
        st.success(f"Confirmed Garmin data imported only into {athlete_name}.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("New runs", activity_result.imported if activity_result else 0)
        c2.metric("Runs enriched", activity_result.enriched if activity_result else 0)
        c3.metric("New health days", health_result.imported)
        c4.metric("Health days enriched", health_result.enriched)
        all_errors = (*activity_issues, *health_result.errors)
        if all_errors:
            with st.expander(f"Import notes ({len(all_errors):,})"):
                for error in all_errors:
                    st.write(f"• {_safe_garmin_error(error)}")


def _show_runalyze_health_import(athlete_id, athlete_name):
    st.markdown("### Runalyze health data")
    st.write(
        "Upload Runalyze’s combined health CSV to connect nightly HRV, "
        "resting heart rate and sleep to Recovery Coach. The standalone HRV "
        "CSV is also accepted."
    )
    st.caption(
        "Health evidence is stored separately from activities, remains assigned "
        "to one athlete and never changes an approved Training Block automatically."
    )
    uploaded_file = st.file_uploader(
        "Upload Runalyze combined health or HRV CSV",
        type=["csv"],
        key="runalyze_health_upload",
    )
    if uploaded_file is None:
        st.info(
            "In Runalyze, download Combined health data when possible. It contains "
            "more useful recovery context than the HRV-only export."
        )
        return
    try:
        frame = pd.read_csv(uploaded_file)
    except Exception as error:
        st.error(f"The health CSV could not be read: {error}")
        return
    parsed = parse_runalyze_health_rows(frame.to_dict(orient="records"))
    if not parsed.records:
        st.error(parsed.issues[0] if parsed.issues else "No usable health rows were found.")
        return

    records = parsed.records
    hrv_count = sum(record.hrv_value is not None for record in records)
    resting_count = sum(record.resting_hr is not None for record in records)
    sleep_count = sum(record.sleep_duration_min is not None for record in records)
    dates = [record.health_date for record in records]
    kind = "Combined health" if parsed.file_kind == "combined_health" else "HRV only"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Usable health days", f"{len(records):,}")
    c2.metric("HRV readings", f"{hrv_count:,}")
    c3.metric("Resting-HR readings", f"{resting_count:,}")
    c4.metric("Sleep records", f"{sleep_count:,}")
    st.success(
        f"{kind} export ready for {athlete_name}: {dates[0]} to {dates[-1]}."
    )
    if parsed.skipped:
        st.info(
            f"{parsed.skipped:,} row(s) without supported recovery evidence will be skipped."
        )
    if parsed.issues:
        with st.expander(f"Rows needing review ({len(parsed.issues):,})"):
            for issue in parsed.issues:
                st.write(f"• {issue}")
    st.info(
        "Repeated uploads are safe. Matching dates are counted as duplicates; "
        "newly available values enrich the existing day."
    )
    confirmation = st.checkbox(
        f"I confirm this health export belongs to {athlete_name}.",
        key="runalyze_health_confirmation",
    )
    if st.button(
        "Import Runalyze Health Data",
        type="primary",
        disabled=not confirmation,
        use_container_width=True,
    ):
        with st.spinner(f"Importing recovery evidence into {athlete_name}…"):
            result = import_runalyze_health_records(
                records,
                athlete_id=athlete_id,
            )
        st.cache_data.clear()
        st.success(f"Runalyze health import complete for {athlete_name}.")
        columns = st.columns(5)
        columns[0].metric("New days", result.imported)
        columns[1].metric("Enriched", result.enriched)
        columns[2].metric("Duplicates", result.duplicates)
        columns[3].metric("Errors", len(result.errors))
        columns[4].metric(
            f"{athlete_name} health days",
            get_athlete_health_count(athlete_id),
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
        [
            "Runalyze CSV",
            "Runalyze Health CSV",
            "Garmin FIT / ZIP",
            "Garmin Connect (Experimental)",
        ],
        horizontal=True,
    )

    if import_type == "Garmin Connect (Experimental)":
        _show_garmin_connect(athlete_id, athlete_name)
        return

    if import_type == "Garmin FIT / ZIP":
        _show_garmin_import(athlete_id, athlete_name)
        return

    if import_type == "Runalyze Health CSV":
        _show_runalyze_health_import(athlete_id, athlete_name)
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
