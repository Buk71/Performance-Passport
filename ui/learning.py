"""Premium athlete-facing Learning Coach."""

from __future__ import annotations

import html

import streamlit as st

from core.cache_version import NAVIGATION_CACHE_TTL_SECONDS, get_athlete_cache_version
from core.learning_coach import LearningCoachDetail, LearningLibraryInsight, build_learning_coach_detail
from core.learning_engine import build_learning_observations
from core.performance_backtracking import build_performance_backtracking_profile
from ui.athlete_selection import render_athlete_id_selector


LEARNING_CACHE_SCHEMA = 1
DEEP_EVIDENCE_CACHE_SCHEMA = 1


@st.cache_data(show_spinner=False, ttl=NAVIGATION_CACHE_TTL_SECONDS)
def _cached_learning_coach(athlete_id: int, schema: int, data_version) -> LearningCoachDetail:
    del schema, data_version
    return build_learning_coach_detail(athlete_id)


@st.cache_data(show_spinner=False, ttl=NAVIGATION_CACHE_TTL_SECONDS)
def _cached_deep_evidence(athlete_id: int, schema: int, data_version):
    del schema, data_version
    return build_learning_observations(athlete_id), build_performance_backtracking_profile(athlete_id)


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _delta(value: float | None) -> str:
    return "Building" if value is None else f"{value:+.1f} pts"


def _rate(value: float | None) -> str:
    return "Building" if value is None else f"{value:.0%}"


def _pattern_cards(detail: LearningCoachDetail) -> str:
    if not detail.profile.patterns:
        return '<div class="learning-empty">Trusted personal response evidence is still building.</div>'
    cards = []
    for pattern in detail.profile.patterns:
        tone = "is-positive" if pattern.direction in {"positive", "strong_positive"} else ""
        cards.append(f"""
        <article class="learning-pattern {tone}">
          <div class="learning-pattern-top"><span>{_escape(pattern.family_label.upper())}</span><b>{_escape(pattern.confidence_label)}</b></div>
          <h3>{_escape(pattern.headline)}</h3><p>{_escape(pattern.explanation)}</p>
          <div class="learning-pattern-grid">
            <div><small>TRUSTED SESSIONS</small><strong>{pattern.trusted_session_count}</strong></div>
            <div><small>RESPONSE WINDOWS</small><strong>{pattern.response_observation_count}</strong></div>
            <div><small>ASSOCIATION</small><strong>{_delta(pattern.average_response_delta)}</strong></div>
            <div><small>POSITIVE RATE</small><strong>{_rate(pattern.positive_response_rate)}</strong></div>
          </div>
          <footer>Observational association · not proof of causation</footer>
        </article>""")
    return "".join(cards)


def _related_cards(detail: LearningCoachDetail) -> str:
    return "".join(f"""
    <article class="learning-related">
      <div class="learning-label">{_escape(item.coach.upper())}</div>
      <h3>{_escape(item.headline)}</h3><p>{_escape(item.explanation)}</p>
      <strong>{_escape(item.action)}</strong>
    </article>""" for item in detail.related_insights)


def build_learning_coach_html(detail: LearningCoachDetail) -> str:
    lesson = detail.daily_lesson
    insight = lesson.insight
    windows = sum(pattern.response_observation_count for pattern in detail.profile.patterns)
    limitations = "".join(f"<li>{_escape(item)}</li>" for item in detail.limitations)
    return f"""
    <main class="learning-shell">
      <section class="learning-hero">
        <div class="learning-intro">
          <div class="learning-eyebrow">YOUR LEARNING COACH · {_escape(detail.reference_date)}</div>
          <h1>Turn today’s evidence into tomorrow’s understanding.</h1>
          <p>One relevant lesson first, then the personal patterns and historical evidence behind it.</p>
          <div class="learning-context"><span>CURRENT CONTEXT</span><strong>{_escape(detail.context_label)}</strong><small>{_escape(lesson.why_today)}</small></div>
          <div class="learning-stats">
            <div><strong>{detail.profile.trusted_workout_count}</strong><span>trusted workouts</span></div>
            <div><strong>{detail.profile.learned_pattern_count}</strong><span>learned families</span></div>
            <div><strong>{windows}</strong><span>response windows</span></div>
            <div><strong>{len(detail.library)}</strong><span>curated lessons</span></div>
          </div>
        </div>
        <aside class="learning-daily">
          <div class="learning-daily-top"><span>TODAY’S LESSON · {_escape(insight.coach.upper())}</span><b>{_escape(lesson.confidence)}</b></div>
          <h2>{_escape(insight.headline)}</h2><p>{_escape(insight.explanation)}</p>
          <div class="learning-action"><span>TRY THIS</span><strong>{_escape(insight.action)}</strong></div>
          <div class="learning-why"><span>WHY IT IS RELEVANT</span><p>{_escape(lesson.why_today)}</p></div>
          <small>{_escape(lesson.personal_evidence)}</small>
        </aside>
      </section>
      <section class="learning-section">
        <div class="learning-heading"><div><div class="learning-eyebrow">WHAT PERFORMANCE PASSPORT HAS LEARNED</div><h2>Personal associations from real training.</h2></div><span>ATHLETE-SPECIFIC · OBSERVATIONAL</span></div>
        <div class="learning-patterns">{_pattern_cards(detail)}</div>
      </section>
      <section class="learning-section">
        <div class="learning-heading"><div><div class="learning-eyebrow">CONTINUE LEARNING</div><h2>Three ideas for the current context.</h2></div><span>{_escape(detail.context_family.upper())}</span></div>
        <div class="learning-related-grid">{_related_cards(detail)}</div>
      </section>
      <details class="learning-method"><summary>Learning Coach guardrails</summary><ul>{limitations}</ul></details>
    </main>
    <style>
      .learning-shell{{--ink:#10263d;color:var(--ink);display:grid;gap:11px;container-type:inline-size}}.learning-shell *{{box-sizing:border-box}}
      .learning-hero,.learning-section,.learning-method{{background:#fff;border:1px solid #e5ddd2;border-radius:19px;box-shadow:0 8px 24px rgba(16,38,61,.045);overflow:hidden}}
      .learning-hero{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(350px,.85fr);min-height:430px}}
      .learning-intro{{padding:35px 36px 28px;display:flex;flex-direction:column;background:radial-gradient(circle at 0 100%,rgba(51,153,111,.08),transparent 38%),#fff}}
      .learning-eyebrow,.learning-label{{color:#70808d;font-size:11px;line-height:1.25;font-weight:850;letter-spacing:.12em}}
      .learning-intro h1{{color:var(--ink)!important;font-size:clamp(35px,4vw,56px);line-height:.98;letter-spacing:-.05em;margin:16px 0 13px;max-width:780px}}
      .learning-intro>p{{color:#667584;font-size:15px;line-height:1.55;margin:0;max-width:690px}}
      .learning-context{{margin-top:28px;padding:16px 17px;border:1px solid #d8e8df;border-radius:14px;background:#eef7f2;display:grid;grid-template-columns:auto 1fr;gap:4px 14px}}
      .learning-context span{{color:#238a52;font-size:10px;font-weight:850;letter-spacing:.1em}}.learning-context strong{{color:var(--ink);font-size:15px;text-align:right}}.learning-context small{{color:#5d7468;font-size:11px;line-height:1.4;grid-column:1/-1}}
      .learning-stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:auto;padding-top:24px}}.learning-stats div{{padding:0 13px;border-right:1px solid #e5ddd2;display:flex;flex-direction:column;gap:4px}}.learning-stats div:first-child{{padding-left:0}}.learning-stats div:last-child{{border-right:0}}.learning-stats strong{{font-size:25px;line-height:1}}.learning-stats span{{color:#74828f;font-size:10px}}
      .learning-daily{{padding:34px 31px 29px;color:#fff!important;background:radial-gradient(circle at 100% 0,rgba(34,125,126,.34),transparent 38%),linear-gradient(145deg,#072640,#0a3548);display:flex;flex-direction:column}}
      .learning-daily-top{{display:flex;justify-content:space-between;gap:12px;align-items:center}}.learning-daily-top span{{color:#7adfba!important;font-size:10px;font-weight:850;letter-spacing:.1em}}.learning-daily-top b{{color:#fff!important;padding:6px 8px;border:1px solid rgba(255,255,255,.17);border-radius:999px;font-size:9px;white-space:nowrap}}
      .learning-daily h2{{color:#fff!important;font-size:clamp(29px,3vw,42px);line-height:1.02;letter-spacing:-.045em;margin:30px 0 14px}}.learning-daily>p{{color:#dce7ec!important;font-size:14px;line-height:1.55;margin:0}}
      .learning-action{{margin:25px 0 0;padding:15px 16px;border-radius:13px;background:#f05a28;display:flex;flex-direction:column;gap:5px}}.learning-action span{{color:#ffe5da!important;font-size:9px;font-weight:850;letter-spacing:.1em}}.learning-action strong{{color:#fff!important;font-size:14px;line-height:1.4}}
      .learning-why{{margin-top:16px;padding-top:15px;border-top:1px solid rgba(255,255,255,.14)}}.learning-why span{{color:#7adfba!important;font-size:9px;font-weight:850;letter-spacing:.1em}}.learning-why p{{color:#d5e2e8!important;font-size:11px;line-height:1.45;margin:6px 0 0}}.learning-daily>small{{color:#9fb4c0!important;font-size:10px;line-height:1.45;margin-top:auto;padding-top:17px}}
      .learning-section{{padding:24px 26px}}.learning-heading{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:17px}}.learning-heading h2{{color:var(--ink)!important;font-size:25px;line-height:1.1;letter-spacing:-.035em;margin:6px 0 0}}.learning-heading>span{{color:#238a52;font-size:10px;font-weight:850;letter-spacing:.09em;white-space:nowrap}}
      .learning-patterns{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}}.learning-pattern{{padding:17px;border:1px solid #e5ddd2;border-radius:14px;background:#fbf9f5}}.learning-pattern.is-positive{{border-top:3px solid #36a36f}}.learning-pattern-top{{display:flex;justify-content:space-between;gap:10px}}.learning-pattern-top span{{color:#71808d;font-size:10px;font-weight:850;letter-spacing:.09em}}.learning-pattern-top b{{color:#238a52;font-size:10px}}.learning-pattern h3{{color:var(--ink)!important;font-size:17px;line-height:1.2;margin:12px 0 6px}}.learning-pattern>p{{color:#687582;font-size:11px;line-height:1.45;min-height:48px;margin:0}}
      .learning-pattern-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:14px}}.learning-pattern-grid div{{border:1px solid #ebe4da;border-radius:10px;background:#fff;padding:9px;display:flex;flex-direction:column;gap:5px;min-width:0}}.learning-pattern-grid small{{color:#7c8994;font-size:8px;line-height:1.3;font-weight:850;letter-spacing:.07em}}.learning-pattern-grid strong{{font-size:13px;line-height:1.2}}.learning-pattern footer{{color:#8a949d;font-size:9px;margin-top:10px}}
      .learning-related-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}}.learning-related{{min-height:190px;padding:17px;border:1px solid #e5ddd2;border-radius:14px;background:#fff;display:flex;flex-direction:column}}.learning-related:first-child{{border-top:3px solid #f05a28}}.learning-related h3{{color:var(--ink)!important;font-size:18px;line-height:1.15;margin:14px 0 7px}}.learning-related p{{color:#687582;font-size:11px;line-height:1.45;margin:0}}.learning-related>strong{{color:#238a52;font-size:11px;line-height:1.4;margin-top:auto;padding-top:14px}}
      .learning-method{{padding:0 20px}}.learning-method summary{{cursor:pointer;padding:16px 0;color:var(--ink);font-size:12px;font-weight:850}}.learning-method ul{{margin:0 0 17px;padding-left:20px}}.learning-method li{{color:#687582;font-size:10px;line-height:1.5;margin:5px 0}}.learning-empty{{min-height:130px;display:grid;place-items:center;color:#73818d;background:#f8f5ef;border-radius:13px;font-size:12px}}
      @container (max-width:900px){{.learning-hero{{grid-template-columns:1fr}}.learning-daily{{min-height:440px}}.learning-pattern-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@container (max-width:650px){{.learning-patterns,.learning-related-grid{{grid-template-columns:1fr}}.learning-heading{{flex-direction:column;gap:7px}}}}@container (max-width:460px){{.learning-intro,.learning-daily,.learning-section{{padding:23px 20px}}.learning-stats{{grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 0}}.learning-context{{grid-template-columns:1fr}}.learning-context strong{{text-align:left}}}}
    </style>"""


def build_learning_library_html(insights: tuple[LearningLibraryInsight, ...], *, topic: str) -> str:
    selected = insights if topic == "All topics" else tuple(item for item in insights if item.topic == topic)
    cards = "".join(f"""
    <article class="library-card"><div class="library-top"><span>{_escape(item.topic.upper())}</span><b>{_escape(item.coach)}</b></div>
      <h3>{_escape(item.headline)}</h3><p>{_escape(item.explanation)}</p>
      <div class="library-action"><small>COACHING ACTION</small><strong>{_escape(item.action)}</strong></div>
      <footer>{_escape(item.basis)} · use individual judgement</footer>
    </article>""" for item in selected)
    return f"""
    <section class="library-shell"><div class="library-heading"><div><span>COACHING LIBRARY</span><h2>Learn the reason behind the run.</h2></div><b>{len(selected)} LESSON{'S' if len(selected)!=1 else ''}</b></div><div class="library-grid">{cards}</div></section>
    <style>
      .library-shell{{color:#10263d;padding:24px 26px;background:#fff;border:1px solid #e5ddd2;border-radius:19px;box-shadow:0 8px 24px rgba(16,38,61,.045);container-type:inline-size}}.library-shell *{{box-sizing:border-box}}
      .library-heading{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:17px}}.library-heading span{{color:#70808d;font-size:11px;font-weight:850;letter-spacing:.12em}}.library-heading h2{{color:#10263d!important;font-size:25px;line-height:1.1;letter-spacing:-.035em;margin:6px 0 0}}.library-heading>b{{color:#238a52;font-size:10px;letter-spacing:.09em}}
      .library-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}}.library-card{{min-height:245px;padding:17px;border:1px solid #e5ddd2;border-radius:14px;background:#fbf9f5;display:flex;flex-direction:column}}.library-top{{display:flex;justify-content:space-between;gap:10px}}.library-top span,.library-top b{{font-size:9px;font-weight:850}}.library-top span{{color:#71808d;letter-spacing:.08em}}.library-top b{{color:#238a52}}.library-card h3{{color:#10263d!important;font-size:18px;line-height:1.15;margin:16px 0 7px}}.library-card>p{{color:#687582;font-size:11px;line-height:1.45;margin:0}}.library-action{{margin-top:auto;padding-top:15px}}.library-action small{{display:block;color:#f05a28;font-size:8px;font-weight:850;letter-spacing:.08em}}.library-action strong{{display:block;font-size:11px;line-height:1.4;margin-top:5px}}.library-card footer{{color:#8a949d;font-size:9px;line-height:1.35;border-top:1px solid #e7e0d7;margin-top:13px;padding-top:9px}}
      @container (max-width:850px){{.library-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@container (max-width:520px){{.library-grid{{grid-template-columns:1fr}}.library-shell{{padding:20px}}.library-heading{{flex-direction:column}}}}
    </style>"""


def _show_deep_evidence(detail: LearningCoachDetail, data_version) -> None:
    observations, backtracking = _cached_deep_evidence(detail.athlete_id, DEEP_EVIDENCE_CACHE_SCHEMA, data_version)
    usable = [item for item in observations if item.response_delta is not None]
    st.markdown("### Historical response observations")
    st.caption("The 21 days before and after each trusted workout are compared. This remains association, not causation.")
    if not usable:
        st.info("Complete before-and-after response windows are still building.")
    for item in sorted(usable, key=lambda value: value.response_delta or -999, reverse=True)[:20]:
        with st.expander(f"{item.activity_date} · {item.activity_title} · {item.response_delta:+.1f} points"):
            st.write(f"Execution {item.execution_score:.1f}/100 · {item.pre_sample_count} preceding and {item.post_sample_count} subsequent trusted workouts.")
    st.markdown("### Preparation before strong performances")
    st.write(backtracking.summary)
    for contrast in backtracking.preparation_contrasts:
        st.markdown(f"**{contrast.metric_label}:** {contrast.successful_average:g} before strong performances vs {contrast.normal_average:g} in ordinary training · {contrast.evidence_label}")
    if backtracking.signature_lifts:
        with st.expander("Workout structures unusually associated with strong performances"):
            for signature in backtracking.signature_lifts[:8]:
                lift = "only seen in successful blocks" if signature.lift is None else f"{signature.lift:.1f}× as common"
                st.markdown(f"- **{signature.workout_signature}** — {lift}")


def show_learning_page() -> None:
    st.markdown("""
    <style>
      [data-testid="stMainBlockContainer"]{max-width:1450px;padding-top:4.25rem;padding-bottom:3rem}[data-testid="stMainBlockContainer"]>[data-testid="stVerticalBlock"],[data-testid="stMainBlockContainer"]>div>[data-testid="stVerticalBlock"]{gap:10px}[data-testid="stHeader"]{background:transparent}[data-testid="stElementContainer"]:has(.learning-selector-marker){display:none}[data-testid="stHorizontalBlock"]:has(.learning-selector-marker){align-items:flex-start;gap:8px}
      .learning-context-strip{min-height:40px;border:1px solid #e5ddd2;border-radius:12px;background:#fff;padding:0 15px;display:flex;align-items:center;justify-content:space-between;gap:14px;color:#10263d;box-shadow:0 5px 18px rgba(16,38,61,.035)}.learning-context-strip strong{font-size:12px;letter-spacing:.12em}.learning-context-strip span{color:#6c7885;font-size:11px}.learning-context-strip em{color:#238a52;font-size:10px;font-style:normal;font-weight:800;letter-spacing:.08em}
      @media(max-width:900px){[data-testid="stHorizontalBlock"]:has(.learning-selector-marker) [data-testid="stColumn"]:last-child{display:none}[data-testid="stHorizontalBlock"]:has(.learning-selector-marker) [data-testid="stColumn"]:first-child{flex:1 1 100%;width:100%}}
    </style>""", unsafe_allow_html=True)
    selector_col, context_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="learning-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_athlete_id_selector(label_visibility="collapsed")
    with context_col:
        st.html('<div class="learning-context-strip"><strong>LEARNING COACH</strong><span>Why does today’s training matter?</span><em>PERSONAL EVIDENCE + CURATED GUIDANCE</em></div>')
    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return
    data_version = get_athlete_cache_version(athlete_id)
    with st.spinner("Choosing today’s lesson from real athlete context…"):
        detail = _cached_learning_coach(athlete_id, LEARNING_CACHE_SCHEMA, data_version)
    st.html(build_learning_coach_html(detail))
    topic = st.selectbox("Browse the coaching library", ("All topics", *detail.topics), key=f"learning_topic_{athlete_id}")
    st.html(build_learning_library_html(detail.library, topic=topic))
    if st.toggle("Load deeper personal learning evidence", value=False, key=f"learning_deep_{athlete_id}"):
        with st.spinner("Reconstructing historical response and strong-performance builds…"):
            _show_deep_evidence(detail, data_version)
