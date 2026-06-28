import datetime
import streamlit as st

from core.database import get_connection


def athlete_full_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()


def add_athlete(first_name, last_name, date_of_birth, sex):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM athletes
        WHERE lower(first_name) = lower(?)
          AND lower(coalesce(last_name, '')) = lower(?)
        """,
        (first_name.strip(), last_name.strip()),
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
        (first_name.strip(), last_name.strip(), str(date_of_birth), sex),
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
        DELETE FROM athletes
        WHERE id = ?
        """,
        (athlete_id,),
    )

    conn.commit()
    conn.close()


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


def get_activity_counts_by_athlete():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            athlete_name,
            COUNT(*) AS activity_count
        FROM activities
        GROUP BY athlete_name
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return {name: count for name, count in rows}


def parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.date(1971, 12, 11)


def show_athletes_page():
    st.title("Athletes")
    st.write("Manage athlete profiles for Performance Passport.")

    activity_counts = get_activity_counts_by_athlete()

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
            activity_count = activity_counts.get(full_name, 0)

            with st.expander(f"{full_name} — {activity_count:,} activities"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Activities", f"{activity_count:,}")

                with col2:
                    st.metric("Sex", sex or "Not set")

                with col3:
                    st.metric("DOB", dob or "Not set")

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
                            "LT1 HR",
                            min_value=0,
                            max_value=250,
                            value=int(lt1_hr or 0),
                            step=1,
                            key=f"lt1_hr_{athlete_id}",
                        )

                        new_lt2_hr = st.number_input(
                            "LT2 HR",
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
                            st.success(f"Updated {new_first_name} {new_last_name}")
                            st.rerun()
                        else:
                            st.error("First name is required.")

                st.warning(
                    "Deleting an athlete removes the registered profile only. "
                    "Imported activities are not deleted."
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
                    delete_athlete(athlete_id)
                    st.success(f"Deleted {full_name}")
                    st.rerun()

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

    st.subheader("Athletes detected from imported activities")

    if not activity_counts:
        st.info("No imported activity athletes found yet.")
    else:
        for athlete_name, activity_count in sorted(activity_counts.items()):
            st.write(f"**{athlete_name}** — {activity_count:,} activities")