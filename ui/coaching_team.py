"""Premium, auditable Coaching Team detail page."""

from __future__ import annotations

import html

import streamlit as st

from core.coaching_team import CoachProfile, CoachingTeamDetail, build_coaching_team_detail
from ui.activity_navigation import activity_review_url
from ui.athlete_selection import (
    SESSION_ID_KEY,
    SESSION_NAME_KEY,
    render_athlete_id_selector,
)
from ui.coaching_navigation import (
    clear_coaching_team_params,
    read_coaching_team_request,
)


COACHING_TEAM_CACHE_SCHEMA = 1


def _safe(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(int(round(seconds)), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _status_text(profile: CoachProfile) -> str:
    if not profile.available:
        return "Building"
    if profile.position:
        return f"{profile.position.title()} view"
    return "Evidence active"


def _fact_html(profile: CoachProfile, athlete_id: int) -> str:
    cards = []
    for fact in profile.facts:
        value = _safe(fact.value)
        if fact.activity_id is not None:
            url = _safe(activity_review_url(athlete_id, fact.activity_id))
            value = (
                f'<a class="ct-evidence-link" href="{url}" target="_self">'
                f'{value}<span>Review run →</span></a>'
            )
        cards.append(
            f"""
            <div class="ct-fact">
                <span>{_safe(fact.label)}</span>
                <strong>{value}</strong>
                <em>{_safe(fact.detail)}</em>
            </div>
            """
        )
    return "".join(cards)


def _list(items: tuple[str, ...], empty: str) -> str:
    values = items or (empty,)
    return "".join(f"<li>{_safe(item)}</li>" for item in values)


def _coach_card(profile: CoachProfile, focused: bool, athlete_id: int) -> str:
    lead = '<span class="ct-lead">Lead opinion</span>' if profile.is_lead else ""
    prediction = (
        f"""
        <div class="ct-prediction">
            <span>Goal estimate</span>
            <strong>{_safe(_clock(profile.predicted_seconds))}</strong>
            <em>{_safe(_status_text(profile))}</em>
        </div>
        """
        if profile.contributes_to_consensus
        else """
        <div class="ct-prediction ct-supporting-result">
            <span>Team role</span>
            <strong>Supporting</strong>
            <em>Not an extra prediction vote</em>
        </div>
        """
    )
    kind = "Prediction coach" if profile.contributes_to_consensus else "Supporting coach"
    confidence_width = max(0, min(profile.confidence * 100, 100))
    return f"""
    <section id="coach-{_safe(profile.key)}"
             class="ct-coach-card {'ct-focused' if focused else ''}">
        <div class="ct-coach-head">
            <div class="ct-avatar">{_safe(profile.code)}</div>
            <div class="ct-coach-identity">
                <span>{_safe(kind)} · {_safe(profile.role)}</span>
                <h3>{_safe(profile.title)}</h3>
            </div>
            {lead}
        </div>
        {prediction}
        <div class="ct-confidence-row">
            <span>Evidence confidence</span>
            <strong>{profile.confidence:.0%}</strong>
        </div>
        <div class="ct-confidence-track">
            <span style="width:{confidence_width:.1f}%"></span>
        </div>
        <p class="ct-summary">{_safe(profile.summary)}</p>
        <div class="ct-facts">{_fact_html(profile, athlete_id)}</div>
        <details class="ct-audit">
            <summary>Open evidence audit <span>{profile.sample_size:,} observations</span></summary>
            <div class="ct-audit-grid">
                <div>
                    <h4>What supports this view</h4>
                    <ul class="ct-strengths">{_list(profile.strengths, 'Evidence is still building.')}</ul>
                </div>
                <div>
                    <h4>What limits this view</h4>
                    <ul class="ct-limits">{_list(profile.limitations, 'No additional limitation recorded.')}</ul>
                </div>
            </div>
        </details>
    </section>
    """


def build_coaching_team_html(
    detail: CoachingTeamDetail,
    *,
    focus_key: str | None = None,
) -> str:
    """Build the complete page as testable, responsive HTML."""
    prediction_cards = "".join(
        _coach_card(profile, profile.key == focus_key, detail.athlete_id)
        for profile in detail.prediction_coaches
    )
    supporting_cards = "".join(
        _coach_card(profile, profile.key == focus_key, detail.athlete_id)
        for profile in detail.supporting_coaches
    )
    notes = "".join(f"<li>{_safe(note)}</li>" for note in detail.notes)
    target = _clock(detail.target_seconds) if detail.target_seconds else "No time target"
    return f"""
    <main class="ct-shell">
        <style>
            .ct-shell {{
                --ct-ink:#08233d; --ct-paper:#fbf8f2; --ct-orange:#f45a2a;
                --ct-green:#23936f; --ct-line:#e3ddd3; color:var(--ct-ink);
                font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
                max-width:1420px; margin:0 auto 48px;
            }}
            .ct-shell * {{ box-sizing:border-box; }}
            .ct-hero {{
                position:relative; overflow:hidden; display:grid;
                grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr);
                gap:24px; padding:34px; border-radius:24px; color:#fff;
                background:linear-gradient(125deg,#071f38 0%,#0b2d4e 68%,#164b5a 100%);
                box-shadow:0 20px 45px rgba(8,35,61,.16);
            }}
            .ct-hero:after {{
                content:""; position:absolute; inset:-60% -10% auto auto;
                width:520px; height:520px; border:1px solid rgba(255,255,255,.12);
                border-radius:48% 52% 46% 54%; transform:rotate(22deg);
                box-shadow:0 0 0 50px rgba(255,255,255,.025),0 0 0 100px rgba(244,90,42,.04);
            }}
            .ct-eyebrow,.ct-section-kicker {{
                color:#87d5bd; font-size:13px; font-weight:850; letter-spacing:.16em;
                text-transform:uppercase;
            }}
            .ct-hero h1 {{
                max-width:800px; margin:12px 0 10px; font-size:clamp(36px,4.2vw,66px);
                line-height:.98; letter-spacing:-.055em; color:#fff !important;
            }}
            .ct-hero-copy {{
                max-width:780px; margin:0; color:#d4dfe7 !important; font-size:18px; line-height:1.52;
            }}
            .ct-hero-copy strong {{ color:#fff !important; }}
            .ct-capability {{
                position:relative; z-index:1; align-self:stretch; padding:22px;
                border:1px solid rgba(255,255,255,.17); border-radius:18px;
                background:rgba(255,255,255,.075); backdrop-filter:blur(8px);
            }}
            .ct-capability > span {{
                display:block; color:#b9c9d5; font-size:12px; font-weight:800;
                letter-spacing:.14em; text-transform:uppercase;
            }}
            .ct-capability > strong {{
                display:block; margin:6px 0 2px; color:#fff; font-size:39px;
                line-height:1; letter-spacing:-.045em;
            }}
            .ct-capability > em {{ color:#87d5bd; font-size:13px; font-style:normal; font-weight:750; }}
            .ct-capability dl {{
                display:grid; grid-template-columns:1fr 1fr; gap:12px;
                margin:20px 0 0; padding-top:17px; border-top:1px solid rgba(255,255,255,.14);
            }}
            .ct-capability dt {{ color:#b2c2cf; font-size:11px; letter-spacing:.12em; text-transform:uppercase; }}
            .ct-capability dd {{ margin:4px 0 0; color:#fff; font-size:15px; font-weight:800; }}
            .ct-consensus {{
                display:grid; grid-template-columns:1.35fr repeat(3,minmax(150px,.55fr));
                gap:10px; margin-top:12px;
            }}
            .ct-consensus > div {{
                padding:17px 19px; border:1px solid var(--ct-line); border-radius:16px;
                background:#fff; box-shadow:0 9px 24px rgba(8,35,61,.055);
            }}
            .ct-consensus .ct-consensus-main {{ border-top:3px solid var(--ct-green); }}
            .ct-consensus span {{
                display:block; margin-bottom:6px; color:#667b8e; font-size:11px;
                font-weight:850; letter-spacing:.14em; text-transform:uppercase;
            }}
            .ct-consensus strong {{ display:block; color:var(--ct-ink) !important; font-size:18px; line-height:1.25; }}
            .ct-consensus-main strong {{ font-size:20px; }}
            .ct-section-head {{
                display:flex; align-items:end; justify-content:space-between; gap:24px;
                margin:34px 2px 15px;
            }}
            .ct-section-head h2 {{ margin:6px 0 0; color:var(--ct-ink) !important; font-size:34px; letter-spacing:-.035em; }}
            .ct-section-head p {{ max-width:600px; margin:0; color:#5d7285; font-size:16px; line-height:1.45; text-align:right; }}
            .ct-coach-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
            .ct-support-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
            .ct-coach-card {{
                min-width:0; padding:21px; border:1px solid var(--ct-line); border-radius:19px;
                background:#fff; box-shadow:0 12px 29px rgba(8,35,61,.065);
                scroll-margin-top:20px;
            }}
            .ct-coach-card.ct-focused {{ outline:3px solid rgba(244,90,42,.42); outline-offset:3px; }}
            .ct-coach-head {{ display:flex; align-items:center; gap:12px; min-height:46px; }}
            .ct-avatar {{
                display:grid; place-items:center; flex:0 0 43px; width:43px; height:43px;
                border-radius:13px; color:#fff; background:var(--ct-ink); font-size:13px;
                font-weight:900; letter-spacing:.08em;
            }}
            .ct-coach-identity {{ min-width:0; flex:1; }}
            .ct-coach-identity span {{ color:#667b8e; font-size:11.5px; line-height:1.35; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
            .ct-coach-identity h3 {{ margin:3px 0 0; color:var(--ct-ink) !important; font-size:22px; letter-spacing:-.025em; }}
            .ct-lead {{
                padding:5px 8px; border-radius:999px; color:#fff; background:var(--ct-orange);
                font-size:10px; font-weight:900; letter-spacing:.08em; text-transform:uppercase;
            }}
            .ct-prediction {{
                display:grid; grid-template-columns:1fr auto; gap:2px 12px; margin:19px 0 14px;
                padding:15px; border-radius:14px; background:var(--ct-paper);
            }}
            .ct-prediction > span {{ color:#667b8e; font-size:11px; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
            .ct-prediction > strong {{ grid-row:1 / 3; grid-column:2; align-self:center; color:var(--ct-ink) !important; font-size:31px; letter-spacing:-.04em; }}
            .ct-prediction > em {{ color:#475f74; font-size:13px; font-style:normal; font-weight:700; }}
            .ct-supporting-result > strong {{ color:var(--ct-green); font-size:20px; }}
            .ct-confidence-row {{ display:flex; justify-content:space-between; color:#536a7e; font-size:13px; font-weight:750; }}
            .ct-confidence-row strong {{ color:var(--ct-ink); }}
            .ct-confidence-track {{ height:5px; margin:7px 0 15px; overflow:hidden; border-radius:99px; background:#e8e4dd; }}
            .ct-confidence-track span {{ display:block; height:100%; border-radius:inherit; background:linear-gradient(90deg,var(--ct-green),#55b89a); }}
            .ct-summary {{ min-height:84px; margin:0 0 16px; color:#415a70; font-size:15px; line-height:1.5; }}
            .ct-facts {{ display:grid; gap:7px; }}
            .ct-fact {{ padding:11px 12px; border:1px solid #ece6dd; border-radius:12px; background:#fdfbf7; }}
            .ct-fact > span {{ display:block; color:#687d8f; font-size:10.5px; font-weight:850; letter-spacing:.11em; text-transform:uppercase; }}
            .ct-fact > strong {{ display:block; margin-top:5px; color:var(--ct-ink) !important; overflow-wrap:anywhere; font-size:14.5px; line-height:1.35; }}
            .ct-fact > em {{ display:block; margin-top:4px; color:#65798b; font-size:12px; font-style:normal; line-height:1.35; }}
            .ct-evidence-link {{ display:flex; justify-content:space-between; gap:8px; color:var(--ct-ink); text-decoration:none; }}
            .ct-evidence-link span {{ flex:0 0 auto; color:var(--ct-green); font-size:10px; }}
            .ct-audit {{ margin-top:14px; border-top:1px solid var(--ct-line); }}
            .ct-audit summary {{
                display:flex; justify-content:space-between; gap:10px; padding-top:13px;
                cursor:pointer; color:var(--ct-ink); font-size:14px; font-weight:850; list-style:none;
            }}
            .ct-audit summary::-webkit-details-marker {{ display:none; }}
            .ct-audit summary span {{ color:#65798b; font-size:12px; font-weight:700; }}
            .ct-audit-grid {{ display:grid; grid-template-columns:1fr; gap:10px; padding-top:12px; }}
            .ct-audit-grid > div {{ padding:12px; border-radius:12px; background:#f7f4ee; }}
            .ct-audit-grid h4 {{ margin:0 0 8px; color:var(--ct-ink) !important; font-size:13px; }}
            .ct-audit-grid ul {{ margin:0; padding-left:18px; color:#52697d; font-size:13px; line-height:1.5; }}
            .ct-audit-grid li + li {{ margin-top:5px; }}
            .ct-trust {{
                display:grid; grid-template-columns:auto 1fr; gap:17px; margin-top:18px;
                padding:21px 24px; border-radius:17px; color:#d8e4ec; background:var(--ct-ink);
            }}
            .ct-trust strong {{ color:#fff !important; font-size:16px; }}
            .ct-trust ul {{ display:flex; flex-wrap:wrap; gap:7px 24px; margin:0; padding-left:18px; font-size:13px; line-height:1.48; }}
            @media (max-width:1100px) {{
                .ct-hero {{ grid-template-columns:1fr; }}
                .ct-consensus {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
                .ct-consensus-main {{ grid-column:1 / -1; }}
                .ct-coach-grid {{ grid-template-columns:1fr; }}
                .ct-summary {{ min-height:0; }}
            }}
            @media (max-width:680px) {{
                .ct-hero {{ padding:24px 20px; border-radius:19px; }}
                .ct-consensus {{ grid-template-columns:1fr; }}
                .ct-consensus-main {{ grid-column:auto; }}
                .ct-section-head {{ display:block; }}
                .ct-section-head p {{ margin-top:8px; text-align:left; }}
                .ct-coach-card {{ padding:17px; }}
                .ct-trust {{ grid-template-columns:1fr; }}
            }}
        </style>

        <section class="ct-hero">
            <div>
                <div class="ct-eyebrow">{_safe(detail.athlete_name)} · {_safe(detail.distance_label)} coaching room</div>
                <h1>One athlete.<br>Five evidence specialists.</h1>
                <p class="ct-hero-copy">
                    The Goal Coach combines three independent prediction views for
                    <strong>{_safe(detail.goal_name)}</strong>. Two supporting coaches explain
                    progress and conditions without being counted as extra votes.
                </p>
            </div>
            <div class="ct-capability">
                <span>Current capability</span>
                <strong>{_safe(_clock(detail.low_seconds))}–{_safe(_clock(detail.high_seconds))}</strong>
                <em>{_safe(_clock(detail.central_seconds))} central · {detail.confidence:.0%} confidence</em>
                <dl>
                    <div><dt>Target</dt><dd>{_safe(target)}</dd></div>
                    <div><dt>Lead</dt><dd>{_safe(detail.lead_coach or 'Building')}</dd></div>
                </dl>
            </div>
        </section>

        <section class="ct-consensus">
            <div class="ct-consensus-main">
                <span>Goal Coach · {_safe(detail.consensus_status)}</span>
                <strong>{_safe(detail.consensus_headline)}</strong>
            </div>
            <div><span>Strongest signal</span><strong>{_safe(detail.strongest_system or 'Building')}</strong></div>
            <div><span>Development signal</span><strong>{_safe(detail.limiting_system or 'Building')}</strong></div>
            <div><span>Direct opinions</span><strong>{len(detail.prediction_coaches)} specialist coaches</strong></div>
        </section>

        <div class="ct-section-head">
            <div><span class="ct-section-kicker">Race consensus</span><h2>The three direct opinions</h2></div>
            <p>Each estimate comes from a separate line of evidence. Open the audit to see exactly what supports—and limits—the opinion.</p>
        </div>
        <div class="ct-coach-grid">{prediction_cards}</div>

        <div class="ct-section-head">
            <div><span class="ct-section-kicker">Athlete context</span><h2>The supporting specialists</h2></div>
            <p>These coaches deepen the story but cannot outvote Race, Workout or Threshold evidence.</p>
        </div>
        <div class="ct-coach-grid ct-support-grid">{supporting_cards}</div>

        <section class="ct-trust">
            <strong>How to read the team</strong>
            <ul>{notes}</ul>
        </section>
    </main>
    """


@st.cache_data(show_spinner=False, ttl=120)
def _cached_team(athlete_id: int, schema: int):
    del schema
    return build_coaching_team_detail(athlete_id)


def _apply_request() -> str | None:
    request = read_coaching_team_request(st.query_params)
    if request is None:
        return None
    st.session_state[SESSION_ID_KEY] = request.athlete_id
    st.session_state.pop(SESSION_NAME_KEY, None)
    clear_coaching_team_params(st.query_params)
    return request.coach_key


def show_coaching_team_page() -> None:
    """Render the selected athlete's auditable Coaching Team."""
    focus_key = _apply_request()
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1480px; padding-top:4rem; }
            [data-testid="stHorizontalBlock"]:has(.ct-selector-marker) { align-items:center; }
            [data-testid="stElementContainer"]:has(.ct-selector-marker) { display:none; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    title_col, selector_col = st.columns([4, 1.35], gap="medium")
    with title_col:
        st.markdown(
            '<span class="ct-selector-marker"></span>',
            unsafe_allow_html=True,
        )
    with selector_col:
        athlete_id = render_athlete_id_selector(label="Athlete")
    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return
    with st.spinner("Assembling the coaching team's real evidence…"):
        detail = _cached_team(athlete_id, COACHING_TEAM_CACHE_SCHEMA)
    if detail is None:
        st.warning("No coaching evidence is available for this athlete yet.")
        return
    st.html(build_coaching_team_html(detail, focus_key=focus_key))
