import streamlit as st

from core.athlete_dna import build_athlete_dna
from core.coach_brain import CoachBrain
from core.database import get_connection
from core.easy_run_coach import build_easy_run_coach
from core.evidence_engine import build_athlete_evidence_profile
from core.performance_dna import build_performance_dna
from ui.athlete_selection import render_athlete_selector
from ui.dashboard import get_athlete_thresholds, get_run_profiles, safe_text

ATTRIBUTE_META = {
    'aerobic': ('AER', 'Aerobic Coach', 'How efficiently you can run aerobically and how that is changing.'),
    'threshold': ('THR', 'Threshold Coach', 'Your ability to sustain strong aerobic work close to threshold.'),
    'speed': ('SPD', 'Speed Coach', 'Rep speed, comparable workouts, recovery and quality volume.'),
    'endurance': ('END', 'Endurance Coach', 'Long-run strength and the ability to carry fitness over distance.'),
    'durability': ('DUR', 'Durability Coach', 'How well pace and efficiency hold as sessions get longer.'),
    'form': ('FORM', 'Readiness & Form', 'Recent training load, freshness and readiness to perform.'),
}


def show_performance_page():
    athlete_id = render_athlete_selector(key='performance_athlete_selector', label='Athlete', label_visibility='collapsed')
    if athlete_id is None:
        st.warning('No athlete selected.')
        return

    focus = str(st.query_params.get('pp_focus', 'aerobic')).lower()
    if focus not in ATTRIBUTE_META:
        focus = 'aerobic'
    label, title, description = ATTRIBUTE_META[focus]

    conn = get_connection()
    evidence_profile = build_athlete_evidence_profile(conn, athlete_id=athlete_id)
    conn.close()

    brain = CoachBrain(athlete_id)
    evidence_bundle = brain.build_evidence()
    prediction = brain.goal_prediction()
    thresholds = get_athlete_thresholds(athlete_id)
    runs = get_run_profiles(athlete_id, thresholds)
    easy = build_easy_run_coach(runs, evidence_profile=evidence_profile)
    consensus_s = prediction.predicted_seconds if prediction.available else None
    dna = build_performance_dna(evidence_bundle, consensus_prediction_s=consensus_s, easy_run_coach=easy)
    athlete_dna = build_athlete_dna(evidence_bundle, consensus_prediction_s=consensus_s)

    score = dna.system_scores.get(focus)
    confidence = dna.system_confidence.get(focus, 0.0)

    st.html(f'''
    <div class="pp-performance-focus">
      <div class="pp-v21-kicker">Performance · {safe_text(title)}</div>
      <div class="pp-performance-focus-head"><div><div class="pp-performance-focus-code">{safe_text(label)}</div><div class="pp-v21-title" style="font-size:2.5rem;">{safe_text(title)}</div></div><div class="pp-performance-focus-score">{f'{score:.0f}' if score is not None else '—'}</div></div>
      <div class="pp-v21-subtitle">{safe_text(description)}</div>
    </div>
    ''')

    if score is None:
        st.info('This specialist score is not connected yet. Performance Passport will not invent one.')
    else:
        st.metric('Current Athlete DNA score', f'{score:.0f}/100')
        st.caption(f'Evidence confidence {confidence:.0%}. This is an explainable Athlete DNA score, not an age grade.')

    st.markdown('### Why this score?')
    matching = [detail for detail in athlete_dna.details if detail.system == focus]
    if matching:
        detail = matching[0]
        st.write(detail.interpretation)
        for contributor in detail.contributors:
            st.write(f'• {contributor}')
    else:
        st.caption('The dedicated specialist page will be expanded during v0.22.')

    st.markdown('### Next design step')
    st.caption('This first version proves the Athlete Card navigation. The full specialist coach page will add trends, strongest evidence, recent comparable sessions and coaching recommendations.')
