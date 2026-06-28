import datetime
import streamlit as st

from core.database import get_connection


def add_athlete(first_name, last_name, date_of_birth, sex):
    conn = get_connection()
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()


def get_athletes():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, first_name, last_name, date_of_birth, sex
        FROM athletes
        WHERE active = 1
        ORDER BY first_name
        """
    )

    athletes = cursor.fetchall()
    conn.close()

    return athletes


def show_athletes_page():
    st.title("Athletes")
    st.write("Add and manage runners using Performance Passport.")

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
        if first_name:
            add_athlete(first_name, last_name, date_of_birth, sex)
            st.success(f"Added {first_name} {last_name}")
        else:
            st.error("First name is required.")

    st.divider()

    st.subheader("Current athletes")

    athletes = get_athletes()

    if not athletes:
        st.info("No athletes added yet.")
    else:
        for athlete in athletes:
            athlete_id, first_name, last_name, dob, sex = athlete
            st.write(f"**{first_name} {last_name}** — {sex}, born {dob}")