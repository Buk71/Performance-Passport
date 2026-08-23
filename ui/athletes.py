import datetime
import streamlit as st

from core.database import (
    clear_personal_best_override,
    clear_threshold_override,
    get_connection,
    get_effective_athlete_thresholds,
    get_personal_best_overrides,
    save_personal_best_override,
    save_threshold_override,
)
from core.threshold_estimation import estimate_athlete_thresholds


def athlete_full_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()


def parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.date(1971, 12, 11)


def display_measurement(value, unit):
    if value is None or value == 0:
        return "Not set"
    return f"{value:g} {unit}"


def display_number(value):
    if value is None or value == 0:
        return "Not set"
    return value


def _parse_official_time(value):
    parts = str(value or "").strip().split(":")
    if len(parts) not in (2, 3) or any(not part.isdigit() for part in parts):
        raise ValueError("Use MM:SS or H:MM:SS for an official race result.")
    numbers = [int(part) for part in parts]
    if numbers[-1] >= 60 or (len(numbers) == 3 and numbers[-2] >= 60):
        raise ValueError("Minutes and seconds must be below 60.")
    seconds = numbers[-1] + numbers[-2] * 60 + (numbers[0] * 3600 if len(numbers) == 3 else 0)
    if seconds <= 0:
        raise ValueError("An official personal best must be greater than zero.")
    return float(seconds)


def _format_official_time(seconds):
    total = int(round(float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def add_athlete(first_name, last_name, date_of_birth, sex):
    conn = get_connection()
    cursor = conn.cursor()

    first_name = first_name.strip()
    last_name = last_name.strip()
    full_name = athlete_full_name(first_name, last_name)

    cursor.execute(
        """
        SELECT id
        FROM athletes
        WHERE lower(first_name) = lower(?)
          AND lower(coalesce(last_name, '')) = lower(?)
        """,
        (first_name, last_name),
    )

    existing = cursor.fetchone()

    if existing:
        conn.close()
        return False

    cursor.execute(
        """
        INSERT INTO athletes (
            first_name,
            last_name,
            date_of_birth,
            sex
        )
        VALUES (?, ?, ?, ?)
        """,
        (first_name, last_name, str(date_of_birth), sex),
    )

    athlete_id = cursor.lastrowid

    if full_name:
        cursor.execute(
            """
            INSERT OR IGNORE INTO athlete_identities (
                athlete_id,
                source,
                external_name,
                is_primary
            )
            VALUES (?, ?, ?, ?)
            """,
            (athlete_id, "manual", full_name, 1),
        )

    conn.commit()
    conn.close()
    return True


def update_athlete(
    athlete_id,
    first_name,
    last_name,
    date_of_birth,
    sex,
    height_cm,
    weight_kg,
    resting_hr,
    max_hr,
    lt1_hr,
    lt2_hr,
    notes,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE athletes
        SET
            first_name = ?,
            last_name = ?,
            date_of_birth = ?,
            sex = ?,
            height_cm = ?,
            weight_kg = ?,
            resting_hr = ?,
            max_hr = ?,
            lt1_hr = ?,
            lt2_hr = ?,
            notes = ?
        WHERE id = ?
        """,
        (
            first_name.strip(),
            last_name.strip(),
            str(date_of_birth),
            sex,
            height_cm,
            weight_kg,
            resting_hr,
            max_hr,
            lt1_hr,
            lt2_hr,
            notes,
            athlete_id,
        ),
    )

    conn.commit()
    conn.close()


def delete_athlete(athlete_id):
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

    linked_activities = cursor.fetchone()[0]

    if linked_activities > 0:
        conn.close()
        return False

    cursor.execute(
        """
        DELETE FROM athlete_identities
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )

    cursor.execute(
        """
        DELETE FROM athletes
        WHERE id = ?
        """,
        (athlete_id,),
    )

    conn.commit()
    conn.close()
    return True


def get_athletes():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            first_name,
            last_name,
            date_of_birth,
            sex,
            height_cm,
            weight_kg,
            resting_hr,
            max_hr,
            lt1_hr,
            lt2_hr,
            notes
        FROM athletes
        ORDER BY first_name, last_name, id
        """
    )

    athletes = cursor.fetchall()
    conn.close()

    return athletes


def get_activity_counts_by_athlete_id():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            athlete_id,
            COUNT(*) AS activity_count
        FROM activities
        WHERE athlete_id IS NOT NULL
        GROUP BY athlete_id
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return {athlete_id: count for athlete_id, count in rows}


def get_athlete_identities():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            athlete_id,
            source,
            external_name,
            external_id,
            is_primary
        FROM athlete_identities
        ORDER BY athlete_id, is_primary DESC, source, external_name
        """
    )

    rows = cursor.fetchall()
    conn.close()

    identities = {}

    for athlete_id, source, external_name, external_id, is_primary in rows:
        identities.setdefault(athlete_id, []).append(
            {
                "source": source,
                "external_name": external_name,
                "external_id": external_id,
                "is_primary": is_primary,
            }
        )

    return identities


def get_detected_activity_names():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            source,
            athlete_name,
            athlete_id,
            COUNT(*) AS activity_count
        FROM activities
        GROUP BY source, athlete_name, athlete_id
        ORDER BY source, athlete_name
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


def show_athletes_page():
    st.title("Athletes")
    st.write("Manage athlete profiles for Performance Passport.")

    activity_counts = get_activity_counts_by_athlete_id()
    athlete_identities = get_athlete_identities()

    st.subheader("Registered athletes")

    athletes = get_athletes()

    if not athletes:
        st.info("No registered athletes found yet.")
    else:
        for athlete in athletes:
            (
                athlete_id,
                first_name,
                last_name,
                dob,
                sex,
                height_cm,
                weight_kg,
                resting_hr,
                max_hr,
                lt1_hr,
                lt2_hr,
                notes,
            ) = athlete

            full_name = athlete_full_name(first_name, last_name)
            activity_count = activity_counts.get(athlete_id, 0)

            with st.expander(f"{full_name} — {activity_count:,} activities"):
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Activities", f"{activity_count:,}")

                with col2:
                    st.metric("Sex", sex or "Not set")

                with col3:
                    st.metric("DOB", dob or "Not set")

                with col4:
                    st.metric("Athlete ID", athlete_id)

                st.divider()

                profile_col1, profile_col2, profile_col3 = st.columns(3)

                with profile_col1:
                    st.write("**Body**")
                    st.write(f"Height: {display_measurement(height_cm, 'cm')}")
                    st.write(f"Weight: {display_measurement(weight_kg, 'kg')}")

                with profile_col2:
                    st.write("**Heart rate**")
                    st.write(f"Resting HR: {display_number(resting_hr)}")
                    st.write(f"Max HR: {display_number(max_hr)}")

                with profile_col3:
                    st.write("**Profile values**")
                    st.write(f"LT1 HR: {display_number(lt1_hr)}")
                    st.write(f"LT2 HR: {display_number(lt2_hr)}")

                st.divider()

                estimate = estimate_athlete_thresholds(athlete_id)
                effective = get_effective_athlete_thresholds(athlete_id)
                st.write("**Threshold evidence**")
                st.caption(
                    "Automatic field estimates remain visible beside profile or "
                    "tested values. The final column is what the coaches use."
                )
                threshold_head = st.columns([1.1, 1, 1, 1])
                threshold_head[0].caption("BOUNDARY")
                threshold_head[1].caption("TRAINING ESTIMATE")
                threshold_head[2].caption("PROFILE / TEST")
                threshold_head[3].caption("USED BY COACHES")

                for label, estimated_point, profile_value, effective_key in (
                    ("LT1", estimate.lt1, lt1_hr, "lt1_hr"),
                    ("LT2", estimate.lt2, lt2_hr, "lt2_hr"),
                ):
                    threshold_row = st.columns([1.1, 1, 1, 1])
                    threshold_row[0].markdown(f"**{label}**")
                    estimated_text = (
                        f"**{estimated_point.value_bpm} bpm**  \n"
                        f"{estimated_point.low_bpm}–{estimated_point.high_bpm} · "
                        f"{estimated_point.confidence}"
                        if estimated_point.value_bpm is not None
                        else "Not enough evidence"
                    )
                    threshold_row[1].markdown(estimated_text)
                    verified_active = effective.get("source") not in {
                        "Athlete profile values",
                        "Estimated from training history",
                        "Not set",
                    }
                    comparison_value = (
                        effective.get(effective_key) if verified_active
                        else profile_value
                    )
                    comparison_source = (
                        effective.get("source") if verified_active
                        else "Athlete profile" if profile_value else None
                    )
                    threshold_row[2].markdown(
                        f"**{comparison_value} bpm**  \n{comparison_source}"
                        if comparison_value else "Not entered or tested"
                    )
                    threshold_row[3].markdown(
                        f"**{effective[effective_key]} bpm**  \n{effective['source']}"
                        if effective.get(effective_key) else "Not available"
                    )

                if estimate.available:
                    st.caption(
                        f"Estimate uses {estimate.reliable_run_count:,} reliable "
                        f"sustained runs · latest evidence "
                        f"{estimate.latest_evidence_date or 'date unavailable'}. "
                        "This is a field estimate, not a laboratory measurement."
                    )
                else:
                    st.info(estimate.limitations[0])

                with st.expander("Tested or coach-assessed threshold override"):
                    st.caption(
                        "Use laboratory, field-test or coach values when available. "
                        "Clearing the override restores profile values, or the "
                        "automatic estimate when profile values are blank."
                    )
                    with st.form(f"athlete_threshold_override_{athlete_id}"):
                        threshold_cols = st.columns(3)
                        tested_lt1 = threshold_cols[0].number_input(
                            "Tested LT1 HR",
                            min_value=0,
                            max_value=250,
                            value=int(effective.get("lt1_hr") or 0),
                        )
                        tested_lt2 = threshold_cols[1].number_input(
                            "Tested LT2 HR",
                            min_value=0,
                            max_value=250,
                            value=int(effective.get("lt2_hr") or 0),
                        )
                        tested_max = threshold_cols[2].number_input(
                            "Tested Max HR",
                            min_value=0,
                            max_value=250,
                            value=int(effective.get("athlete_max_hr") or 0),
                        )
                        tested_source = st.selectbox(
                            "Evidence source",
                            [
                                "Laboratory test", "Field test",
                                "Coach assessment", "Known personal value", "Other",
                            ],
                        )
                        tested_date = st.date_input(
                            "Test or assessment date",
                            value=datetime.date.today(),
                            key=f"threshold_test_date_{athlete_id}",
                        )
                        tested_notes = st.text_input(
                            "Optional threshold note",
                            key=f"threshold_notes_{athlete_id}",
                        )
                        save_col, clear_col = st.columns(2)
                        save_test = save_col.form_submit_button(
                            "Save and use tested values", type="primary"
                        )
                        clear_test = clear_col.form_submit_button(
                            "Clear tested override"
                        )
                    if save_test:
                        if tested_lt1 and tested_lt2 and tested_lt1 >= tested_lt2:
                            st.error("LT1 must be lower than LT2.")
                        elif tested_lt2 and tested_max and tested_lt2 >= tested_max:
                            st.error("LT2 must be lower than Max HR.")
                        else:
                            save_threshold_override(
                                athlete_id=athlete_id,
                                lt1_hr=tested_lt1 or None,
                                lt2_hr=tested_lt2 or None,
                                max_hr=tested_max or None,
                                source=tested_source,
                                tested_at=str(tested_date),
                                notes=tested_notes.strip() or None,
                            )
                            st.cache_data.clear()
                            st.rerun()
                    if clear_test:
                        clear_threshold_override(athlete_id)
                        st.cache_data.clear()
                        st.rerun()

                st.divider()

                st.write("**Known identities**")

                identities = athlete_identities.get(athlete_id, [])

                if not identities:
                    st.info("No identities recorded yet.")
                else:
                    for identity in identities:
                        label = "⭐ Primary identity" if identity["is_primary"] else "Alias"
                        external_id = (
                            f" — ID: {identity['external_id']}"
                            if identity["external_id"]
                            else ""
                        )

                        st.write(label)
                        st.write(
                            f"`{identity['source']}` → "
                            f"**{identity['external_name']}**"
                            f"{external_id}"
                        )

                st.divider()
                st.write("**Official race personal bests**")
                st.caption(
                    "Use the official chip result when a watch's measured "
                    "distance or elapsed time differs. This takes priority on "
                    "the Athlete Passport card without changing imported runs."
                )
                official_bests = get_personal_best_overrides(athlete_id)
                for event_key, event_label in (
                    ("5k", "5K"), ("10k", "10K"), ("half_marathon", "Half marathon")
                ):
                    current = official_bests.get(event_key)
                    with st.form(f"official_pb_{athlete_id}_{event_key}"):
                        value_col, save_col, clear_col = st.columns([3, 1, 1])
                        result_text = value_col.text_input(
                            f"{event_label} official time",
                            value=_format_official_time(current["official_time_s"]) if current else "",
                            placeholder="19:04" if event_key == "5k" else "1:29:45",
                        )
                        save_pb = save_col.form_submit_button("Save")
                        clear_pb = clear_col.form_submit_button("Clear")
                    if save_pb:
                        try:
                            save_personal_best_override(
                                athlete_id, event_key, _parse_official_time(result_text)
                            )
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.cache_data.clear()
                            st.rerun()
                    if clear_pb:
                        clear_personal_best_override(athlete_id, event_key)
                        st.cache_data.clear()
                        st.rerun()

                st.divider()

                with st.form(f"edit_athlete_{athlete_id}"):
                    edit_col1, edit_col2 = st.columns(2)

                    with edit_col1:
                        new_first_name = st.text_input(
                            "First name",
                            value=first_name or "",
                            key=f"first_name_{athlete_id}",
                        )

                        new_last_name = st.text_input(
                            "Last name",
                            value=last_name or "",
                            key=f"last_name_{athlete_id}",
                        )

                        new_dob = st.date_input(
                            "Date of birth",
                            value=parse_date(dob),
                            min_value=datetime.date(1900, 1, 1),
                            max_value=datetime.date.today(),
                            key=f"dob_{athlete_id}",
                        )

                        new_sex = st.selectbox(
                            "Sex",
                            ["Male", "Female", "Other"],
                            index=["Male", "Female", "Other"].index(sex)
                            if sex in ["Male", "Female", "Other"]
                            else 0,
                            key=f"sex_{athlete_id}",
                        )

                    with edit_col2:
                        new_height_cm = st.number_input(
                            "Height cm",
                            min_value=0.0,
                            max_value=250.0,
                            value=float(height_cm or 0),
                            step=0.5,
                            key=f"height_{athlete_id}",
                        )

                        new_weight_kg = st.number_input(
                            "Weight kg",
                            min_value=0.0,
                            max_value=250.0,
                            value=float(weight_kg or 0),
                            step=0.5,
                            key=f"weight_{athlete_id}",
                        )

                        new_resting_hr = st.number_input(
                            "Resting HR",
                            min_value=0,
                            max_value=250,
                            value=int(resting_hr or 0),
                            step=1,
                            key=f"resting_hr_{athlete_id}",
                        )

                        new_max_hr = st.number_input(
                            "Max HR",
                            min_value=0,
                            max_value=250,
                            value=int(max_hr or 0),
                            step=1,
                            key=f"max_hr_{athlete_id}",
                        )

                        new_lt1_hr = st.number_input(
                            "Profile LT1 HR (optional)",
                            min_value=0,
                            max_value=250,
                            value=int(lt1_hr or 0),
                            step=1,
                            key=f"lt1_hr_{athlete_id}",
                        )

                        new_lt2_hr = st.number_input(
                            "Profile LT2 HR (optional)",
                            min_value=0,
                            max_value=250,
                            value=int(lt2_hr or 0),
                            step=1,
                            key=f"lt2_hr_{athlete_id}",
                        )

                    new_notes = st.text_area(
                        "Notes",
                        value=notes or "",
                        key=f"notes_{athlete_id}",
                    )

                    save_changes = st.form_submit_button("Save changes")

                    if save_changes:
                        if new_first_name.strip():
                            update_athlete(
                                athlete_id,
                                new_first_name,
                                new_last_name,
                                new_dob,
                                new_sex,
                                new_height_cm or None,
                                new_weight_kg or None,
                                new_resting_hr or None,
                                new_max_hr or None,
                                new_lt1_hr or None,
                                new_lt2_hr or None,
                                new_notes,
                            )
                            st.success(
                                f"Updated {new_first_name.strip()} "
                                f"{new_last_name.strip()}"
                            )
                            st.rerun()
                        else:
                            st.error("First name is required.")

                if activity_count == 0:
                    st.warning(
                        "Deleting an athlete removes the registered profile and identities."
                    )

                    confirm_delete = st.checkbox(
                        f"Confirm delete {full_name}",
                        key=f"confirm_delete_{athlete_id}",
                    )

                    if st.button(
                        f"Delete {full_name}",
                        key=f"delete_{athlete_id}",
                        disabled=not confirm_delete,
                    ):
                        deleted = delete_athlete(athlete_id)

                        if deleted:
                            st.success(f"Deleted {full_name}")
                            st.rerun()
                        else:
                            st.error(
                                "This athlete has linked activities and cannot be deleted."
                            )
                else:
                    st.info(
                        "This athlete has linked activities, so the profile cannot "
                        "be deleted without first reassigning or unlinking those activities."
                    )

    st.divider()

    st.subheader("Add athlete")

    with st.form("add_athlete_form"):
        first_name = st.text_input("First name")
        last_name = st.text_input("Last name")

        date_of_birth = st.date_input(
            "Date of birth",
            value=datetime.date(1971, 12, 11),
            min_value=datetime.date(1900, 1, 1),
            max_value=datetime.date.today(),
        )

        sex = st.selectbox(
            "Sex",
            ["Male", "Female", "Other"],
        )

        submitted = st.form_submit_button("Add athlete")

    if submitted:
        if first_name.strip():
            added = add_athlete(first_name, last_name, date_of_birth, sex)

            if added:
                st.success(f"Added {first_name.strip()} {last_name.strip()}")
                st.rerun()
            else:
                st.warning(
                    f"{first_name.strip()} {last_name.strip()} already exists."
                )
        else:
            st.error("First name is required.")

    st.divider()

    st.subheader("Detected activity identities")

    detected_names = get_detected_activity_names()

    if not detected_names:
        st.info("No imported activity identities found yet.")
    else:
        for source, athlete_name, linked_athlete_id, activity_count in detected_names:
            if linked_athlete_id:
                st.write(
                    f"✓ `{source}` → **{athlete_name}** "
                    f"linked to athlete_id `{linked_athlete_id}` "
                    f"({activity_count:,} activities)"
                )
            else:
                st.warning(
                    f"`{source}` → **{athlete_name}** is not linked "
                    f"({activity_count:,} activities)"
                )
