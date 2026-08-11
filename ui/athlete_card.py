from __future__ import annotations

import base64
import datetime
import html
from pathlib import Path

import streamlit as st

from core.database import get_connection

ROOT = Path(__file__).resolve().parents[1]


def _safe(value):
    return html.escape(str(value or ''))


def _image_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    mime = 'image/jpeg' if path.suffix.lower() in {'.jpg', '.jpeg'} else 'image/png'
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'data:{mime};base64,{encoded}'


def _athlete_identity(athlete_id: int):
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT first_name, last_name, date_of_birth, sex
        FROM athletes
        WHERE id = ?
        ''',
        (athlete_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return {'first_name': 'Athlete', 'last_name': '', 'age': None, 'sex': ''}

    first_name, last_name, dob, sex = row
    age = None
    if dob:
        try:
            born = datetime.date.fromisoformat(str(dob)[:10])
            today = datetime.date.today()
            age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except ValueError:
            pass

    return {
        'first_name': first_name or 'Athlete',
        'last_name': last_name or '',
        'age': age,
        'sex': sex or '',
    }


def _profile_score(system_scores: dict[str, float]) -> int | None:
    values = [float(v) for v in system_scores.values() if v is not None and float(v) > 0]
    if not values:
        return None
    return int(round(sum(values) / len(values)))



def build_athlete_card_html(*, athlete_id: int, performance_dna, aerobic_progress_percent: float | None):
    identity = _athlete_identity(athlete_id)
    full_name = f"{identity['first_name']} {identity['last_name']}".strip()
    profile_score = _profile_score(performance_dna.system_scores)

    photo_path = ROOT / 'assets' / 'athletes' / 'richard_burke.jpg' if athlete_id == 1 else None
    photo_uri = _image_data_uri(photo_path) if photo_path is not None else None
    initials = f"{identity['first_name'][:1]}{identity['last_name'][:1]}".upper()

    if photo_uri:
        photo_markup = f'<img class="pp-athlete-photo" src="{photo_uri}" alt="{_safe(full_name)}">'
    else:
        photo_markup = f'<div class="pp-athlete-initials">{_safe(initials)}</div>'

    age_text = str(identity['age']) if identity['age'] is not None else '—'
    sex_prefix = identity['sex'][:1].upper() if identity['sex'] else ''

    scores = performance_dna.system_scores or {}
    attrs = (
        ('AER', 'aerobic', scores.get('aerobic')),
        ('THR', 'threshold', scores.get('threshold')),
        ('SPD', 'speed', scores.get('speed')),
        ('END', 'endurance', scores.get('endurance')),
        ('DUR', 'durability', None),
        ('FORM', 'form', None),
    )

    attr_markup = []
    for label, focus, value in attrs:
        value_text = f'{value:.0f}' if value is not None else '—'
        attr_markup.append(
            f'<a class="pp-athlete-attribute" href="?pp_page=Performance&pp_focus={focus}" '
            f'target="_self" title="Open {label} coach"><span>{label}</span>'
            f'<strong>{value_text}</strong></a>'
        )

    progress_value = f'{aerobic_progress_percent:+.1f}%' if aerobic_progress_percent is not None else 'Building'
    progress_class = 'positive' if aerobic_progress_percent is not None and aerobic_progress_percent >= 0 else ''

    return f"""
    <section class="pp-athlete-card">
      <a class="pp-athlete-score-link" href="?pp_page=Passport" target="_self" title="Open full Performance Passport">
        <div class="pp-athlete-score">
          <strong>{profile_score if profile_score is not None else '—'}</strong>
          <span>PROFILE</span>
        </div>
      </a>
      <div class="pp-athlete-visual">
        <div class="pp-athlete-contours"></div>
        <div class="pp-athlete-road"></div>
        {photo_markup}
        <div class="pp-athlete-identity">
          <strong>{_safe(full_name)}</strong>
          <span>{_safe(sex_prefix)}{_safe(age_text)} · RUNNER</span>
        </div>
      </div>
      <div class="pp-athlete-attributes">{''.join(attr_markup)}</div>
      <a class="pp-athlete-progress" href="?pp_page=Performance&pp_focus=aerobic" target="_self">
        <span>AEROBIC PROGRESS</span>
        <strong class="{progress_class}">{_safe(progress_value)}</strong>
        <small>90-day trend</small>
      </a>
    </section>
    """


def render_athlete_card(*, athlete_id: int, performance_dna, aerobic_progress_percent: float | None):
    st.html(
        build_athlete_card_html(
            athlete_id=athlete_id,
            performance_dna=performance_dna,
            aerobic_progress_percent=aerobic_progress_percent,
        )
    )
