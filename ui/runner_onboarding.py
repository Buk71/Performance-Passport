"""Premium, optional runner-profile editor. Does not modify coaching or plans."""

import streamlit as st

from core.runner_profile import get_runner_profile, save_runner_profile
from core.runner_profile_ui_contract import EXPERIENCE_CHOICES, STATUS_CHOICES, profile_defaults


_PROFILE_STYLES = """
<style>
.pp-profile-hero {
  padding: 25px 28px 22px; border-radius: 17px;
  background: linear-gradient(125deg, #10263D 0%, #19354C 76%, #23465A 100%);
  color: #F7F3EC; position: relative; overflow: hidden;
  border-bottom: 4px solid #F05A28;
}
.pp-profile-hero::after {
  content: ''; position: absolute; width: 190px; height: 190px;
  border: 1px solid rgba(247,243,236,.12); border-radius: 50%;
  right: -55px; top: -115px; box-shadow: 0 0 0 22px rgba(247,243,236,.025),
  0 0 0 45px rgba(247,243,236,.025);
  pointer-events: none;
}
.pp-profile-eyebrow {font-size: 11px; letter-spacing: .16em; font-weight: 750;
  text-transform: uppercase; color: #FFAE8D; margin-bottom: 8px;}
.pp-profile-hero h2, .pp-profile-hero h2 * {font-size: clamp(23px, 3vw, 32px); line-height: 1.16;
  letter-spacing: -.025em; color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF; margin: 0 0 9px;}
.pp-profile-hero p {font-size: 14px; line-height: 1.55; color: #DFE5E7;
  margin: 0; max-width: 610px;}
.pp-profile-step {display:flex; align-items:center; gap:12px; padding: 12px 0 3px;}
.pp-profile-number {background:#F05A28; color:white; width:30px; height:30px;
  flex:0 0 30px; border-radius:9px; display:grid; place-items:center;
  font-size:13px; font-weight:800;}
.pp-profile-step-title {font-weight:750; font-size:16px; color:inherit;}
.pp-profile-step-hint {font-size:12px; opacity:.75; margin-top:2px;}
.pp-profile-saved {padding: 14px 18px; border: 1px solid #D8E5DE;
  border-left: 4px solid #3E8E72; border-radius: 11px;
  background: rgba(62,142,114,.065); margin: 14px 0 8px;}
.pp-profile-saved-label {color:#3E8E72; font-size:11px;
  font-weight:800; text-transform:uppercase; letter-spacing:.1em;}
.pp-profile-saved-value {font-size:13px; line-height:1.6; margin-top:5px;}
.pp-profile-footer {font-size:12px; opacity:.75; line-height:1.55;
  padding: 10px 0 2px;}
@media(max-width: 600px) {
  .pp-profile-hero {padding: 21px 19px;}
  .pp-profile-hero p {font-size: 13px;}
}
</style>
"""


def _step(number, title, hint):
    st.markdown(
        f'<div class="pp-profile-step"><span class="pp-profile-number">{number}</span>'
        f'<div><div class="pp-profile-step-title">{title}</div>'
        f'<div class="pp-profile-step-hint">{hint}</div></div></div>',
        unsafe_allow_html=True,
    )


def show_runner_profile_editor(athlete_id):
    """Edit self-reported context, without changing goals or training plans."""
    st.markdown(_PROFILE_STYLES, unsafe_allow_html=True)
    st.markdown(
        '<div class="pp-profile-hero">'
        '<div class="pp-profile-eyebrow">My Passport / Runner profile</div>'
        '<h2>Your running. Your starting point.</h2>'
        '<p>Help your coaching team understand the runner behind the numbers. '
        'Your history, personal bests and training plans stay yours.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    profile = profile_defaults(get_runner_profile(athlete_id))
    is_complete = all(value is not None for value in profile.values())
    if is_complete:
        summary = (
            f'{EXPERIENCE_CHOICES.get(profile["experience"], "Experience saved")} · '
            f'{STATUS_CHOICES.get(profile["training_status"], "Status saved")} · '
            f'{profile["sessions_per_week"]} days available per week'
        )
        # Values are selected from fixed, trusted option labels; avoid HTML interpolation.
        st.markdown(
            '<div class="pp-profile-saved">'
            '<div class="pp-profile-saved-label">Profile saved</div>'
            '<div class="pp-profile-saved-value">Your preferences are ready to guide future onboarding.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption(summary)
    else:
        st.caption("A few quick choices. You can change these at any time.")

    with st.form(f"runner_profile_{athlete_id}", border=False):
        _step("01", "Your running background", "Experience is about your history, not your current fitness.")
        experience_options = [None, *EXPERIENCE_CHOICES]
        experience = st.selectbox(
            "How would you describe your running experience?",
            experience_options,
            index=experience_options.index(profile["experience"]),
            format_func=lambda value: EXPERIENCE_CHOICES[value] if value else "Choose your experience",
        )

        _step("02", "Where you are today", "A break doesn't erase years of running experience.")
        status_options = [None, *STATUS_CHOICES]
        status = st.selectbox(
            "What best describes your training right now?",
            status_options,
            index=status_options.index(profile["training_status"]),
            format_func=lambda value: STATUS_CHOICES[value] if value else "Choose your current situation",
        )

        _step("03", "Your weekly rhythm", "Choose what fits your life, not what you think you should do.")
        sessions_options = [None, *range(1, 8)]
        sessions = st.selectbox(
            "How many days per week could you usually run?",
            sessions_options,
            index=sessions_options.index(profile["sessions_per_week"]),
            format_func=lambda value: f"{value} day{'s' if value != 1 else ''}" if value else "Choose when ready",
        )
        st.markdown(
            '<div class="pp-profile-footer">Your availability is not a training prescription. '
            'Saving your profile will not alter an existing goal or plan.</div>',
            unsafe_allow_html=True,
        )
        submitted = st.form_submit_button(
            "Save my running profile", type="primary", use_container_width=True
        )

    if submitted:
        if experience is None or status is None or sessions is None:
            st.warning("Please answer all three questions before saving.")
        else:
            save_runner_profile(
                athlete_id,
                experience=experience,
                training_status=status,
                sessions_per_week=sessions,
            )
            st.success("Profile saved. Your goals and training plans haven't changed.")
            st.rerun()
