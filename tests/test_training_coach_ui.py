from core.adaptive_coach_live import LiveCoachDecision
from core.session_designer import DesignedSession
from core.training_coach import (
    TrainingAdjustment,
    TrainingCoachDetail,
    build_training_coach_detail,
)
from ui.next_run import build_training_coach_html


def _decision(athlete_id=1):
    return LiveCoachDecision(
        athlete_id=athlete_id,
        immediate_label="Easy Aerobic",
        immediate_timing="Today",
        immediate_detail="40–50 minutes conversational running.",
        key_family="threshold",
        key_label="Threshold Development",
        key_prescription="5 × 1 km controlled, 90 sec recovery",
        key_day="Thursday",
        confidence=.84,
        confidence_label="Good",
        headline="Easy running is next; threshold remains the key workout.",
        why=("The saved week protects spacing between demanding days.",),
        safety_notes=("Review the session if unusual fatigue persists.",),
        readiness_required=True,
        source="Saved Training Block + Adaptive Coach",
        operational_week_number=3,
        operational_status="On course",
        operational_completed_miles=18.2,
        operational_planned_miles=39.7,
    )


def _session(athlete_id=1):
    return DesignedSession(
        athlete_id=athlete_id,
        family="threshold",
        family_label="Threshold Development",
        icon="",
        purpose="Develop sustainable speed for the active 10K goal.",
        warmup=("15 minutes easy", "4 relaxed strides"),
        main_set=("5 × 1 km controlled, 90 sec recovery",),
        cooldown=("10 minutes easy",),
        pace_low_s_per_km=235.0,
        pace_high_s_per_km=239.0,
        hr_low=152,
        hr_high=161,
        rpe_low=6.0,
        rpe_high=7.0,
        success_looks_like="The final repetition remains controlled.",
        common_mistake="Turning the first repetition into a race.",
        coach_tip="Settle first; earn the final repetition.",
        why_this_session=("Threshold is the current development priority.",),
        historical_evidence=(),
        historical_summary="Three comparable personal sessions support the targets.",
        source="Personal history",
        confidence=.84,
        confidence_label="Good",
        earliest_timing="Thursday",
        readiness_required=True,
        block_name="10K Development",
        block_phase="Capacity",
        goal_name="Sub 39:00",
    )


def _detail(athlete_id=1):
    return TrainingCoachDetail(
        athlete_id=athlete_id,
        decision=_decision(athlete_id),
        session=_session(athlete_id),
        fuel_demand="Quality",
        fuel_focus="Performance day: place useful carbohydrate around the session.",
        fuel_before="Choose a familiar meal or snack.",
        fuel_during="Water is usually enough for shorter sessions.",
        fuel_after="Pair carbohydrate and protein after training.",
        adjustments=(
            TrainingAdjustment("fatigue", "Unusually fatigued", "Move the demanding session."),
            TrainingAdjustment("pain", "Pain or altered movement", "Stop if pain changes gait."),
            TrainingAdjustment("time", "Short of time", "Reduce main-set volume, not recovery."),
        ),
    )


def test_training_coach_page_has_the_complete_premium_journey():
    markup = build_training_coach_html("Richard Burke", _detail())

    for expected in (
        "Richard Burke",
        "Easy Aerobic",
        "Next key session",
        "Threshold Development",
        "Warm-up",
        "Main set",
        "Cool-down",
        "Pace",
        "Heart rate",
        "Effort",
        "Success looks like",
        "Coach’s cue",
        "Why this session",
        "Nutrition Coach",
        "Adapt if needed",
        "Readiness data is not connected",
        "Current safeguards",
    ):
        assert expected in markup

    assert "6:18/mi–6:25/mi" in markup
    assert "152–161 bpm" in markup
    assert "18.2 of 39.7 mi" in markup
    assert "readiness score" not in markup.lower()


def test_training_coach_markup_escapes_athlete_content():
    markup = build_training_coach_html("A <script>alert(1)</script>", _detail())
    assert "<script>" not in markup
    assert "A &lt;script&gt;alert(1)&lt;/script&gt;" in markup


def test_training_coach_composes_existing_services_without_new_decision_formula(monkeypatch):
    decision = _decision(3)
    session = _session(3)
    calls = {}

    def fake_live(athlete_id, *, today=None):
        calls["live"] = (athlete_id, today)
        return decision

    def fake_session(athlete_id, **kwargs):
        calls["session"] = (athlete_id, kwargs)
        return session

    monkeypatch.setattr("core.training_coach.build_live_coach_decision", fake_live)
    monkeypatch.setattr("core.training_coach.build_designed_session", fake_session)

    detail = build_training_coach_detail(3)

    assert detail is not None
    assert detail.athlete_id == 3
    assert detail.decision is decision
    assert detail.session is session
    assert calls["live"][0] == 3
    assert calls["session"][0] == 3
    assert calls["session"][1]["family_override"] == "threshold"
    assert calls["session"][1]["main_set_override"] == (
        "5 × 1 km controlled, 90 sec recovery",
    )
    assert detail.fuel_demand == "Easy"


def test_training_coach_does_not_cross_athlete_content():
    richard = build_training_coach_html("Richard Burke", _detail(1))
    jo = build_training_coach_html("Joanne Burke", _detail(3))

    assert "Richard Burke" in richard
    assert "Joanne Burke" not in richard
    assert "Joanne Burke" in jo
    assert richard != jo
