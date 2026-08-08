import datetime
import html
import textwrap

import streamlit as st

from core.journal import build_latest_journal_entry
from ui.athlete_selection import render_athlete_selector


def _safe(value):
    return html.escape(str(value or ""))


def _html(markup):
    st.html(textwrap.dedent(markup).strip())


def _date_text(value):
    if not value:
        return "Latest run"

    try:
        parsed = datetime.date.fromisoformat(str(value)[:10])
        return parsed.strftime("%a %-d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def _journal_card(icon, label, title, detail):
    _html(
        f"""
        <div class="pp-card" style="margin-top:0.7rem;">
            <div class="pp-card-label">{_safe(icon)} {_safe(label)}</div>
            <div class="pp-card-title">{_safe(title)}</div>
            <div class="pp-card-copy">{_safe(detail)}</div>
        </div>
        """
    )


def show_journal_page():
    st.title("📓 Coach's Journal")
    st.write(
        "A 30-second coaching note for your latest run: recognise what went "
        "well, understand why it matters, and see the next focus."
    )

    athlete_id = render_athlete_selector(
        key="journal_athlete_selector",
        label="Athlete",
    )

    if athlete_id is None:
        st.info("Add an athlete before opening the Coach's Journal.")
        return

    with st.spinner("Writing today's coaching note..."):
        entry = build_latest_journal_entry(athlete_id)

    if entry is None:
        st.info(
            "The Journal needs at least one recognised running activity."
        )
        return

    _html(
        f"""
        <div class="pp-card pp-card-accent">
            <div class="pp-card-label">
                {_safe(_date_text(entry.activity_date))}
            </div>
            <div class="pp-card-title">
                {_safe(entry.journal_title)}
            </div>
            <div class="pp-card-copy" style="font-weight:700; margin-top:0.25rem;">
                {_safe(entry.activity_title)}
            </div>
            <div class="pp-card-copy">
                {_safe(entry.category or "Run")}
                {' · #' + str(entry.recognition_rank) + ' of ' + str(entry.recognition_total)
                 if entry.recognition_rank and entry.recognition_total else ''}
            </div>
        </div>
        """
    )

    left, right = st.columns(2, gap="medium")

    with left:
        _journal_card(
            "🎉",
            "Today's Win",
            entry.todays_win,
            entry.todays_win_detail,
        )

        _journal_card(
            "📅",
            "Block Progress",
            entry.block_progress,
            entry.block_progress_detail,
        )

    with right:
        _journal_card(
            "💡",
            "Next Opportunity",
            entry.next_opportunity,
            entry.next_opportunity_detail,
        )

        _journal_card(
            "➡️",
            "Next Focus",
            entry.next_focus,
            entry.next_focus_detail,
        )

    st.markdown("### 🔎 What changed today?")

    changed_items = "".join(
        f"<li>{_safe(item)}</li>"
        for item in entry.what_changed
    )

    _html(
        f"""
        <div class="pp-card">
            <ul style="margin:0; padding-left:1.2rem; line-height:1.7;">
                {changed_items}
            </ul>
        </div>
        """
    )

    st.markdown("### 🧠 Coach's Note")

    _html(
        f"""
        <div class="pp-card pp-card-hero">
            <div class="pp-card-copy" style="font-size:0.98rem;">
                {_safe(entry.coach_note)}
            </div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">
                    Evidence confidence {entry.evidence_confidence:.0%}
                </span>
            </div>
        </div>
        """
    )

    st.caption(
        "Recognition before recommendation. Every run has something to celebrate."
    )
