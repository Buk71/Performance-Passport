import datetime
from pathlib import Path
from types import SimpleNamespace

from core.goal_coach import GoalCoachDetail, build_goal_coach_detail
from core.goals import GoalHierarchy, GoalHierarchyItem
from ui.goals import build_goal_coach_html


ROOT = Path(__file__).resolve().parent.parent


def _primary(athlete_id=1):
    return GoalHierarchyItem(
        id=7,
        athlete_id=athlete_id,
        name="Sub 39:00",
        goal_type="10K",
        distance_m=10000.0,
        target_time_s=2340.0,
        target_date="2026-11-29",
        race_name="Leeds Abbey Dash",
        priority="Primary",
        status="Active",
        motivation="Turn consistent training into a controlled sub-39 race.",
        training_block_id=4,
        role="Primary",
        influence_title="Drives current coaching",
        influence_summary="Sets the direction for every active coach.",
        block_relationship="Drives 10K Development",
        timing_label="13 weeks away",
        days_to_goal=95,
    )


def _hierarchy(athlete_id=1, *, primary=True):
    return GoalHierarchy(
        athlete_id=athlete_id,
        primary=_primary(athlete_id) if primary else None,
        secondary=(),
        future=(),
        past=(),
        active_block_id=4,
        active_block_name="10K Development",
        headline="Sub 39:00 leads your coaching" if primary else "Choose one goal",
        summary="One Primary goal sets direction.",
        warnings=(),
    )


def _predictions(athlete_id=1, *, available=True):
    return SimpleNamespace(
        athlete_id=athlete_id,
        available=available,
        distance_label="10K",
        low_seconds=2293.0 if available else None,
        high_seconds=2393.0 if available else None,
        central_seconds=2343.0 if available else None,
        target_probability=.47 if available else None,
        confidence=.83 if available else 0.0,
        target_gap_seconds=3.0 if available else None,
        lead_coach="Threshold Coach" if available else None,
        strongest_system="Threshold" if available else None,
        limiting_system="Endurance" if available else None,
        consensus_headline="The coaches broadly agree, with useful differences in confidence.",
    )


def _summary(athlete_id=1):
    return SimpleNamespace(
        athlete_id=athlete_id,
        block_name="10K Development",
        block_context="Capacity · Week 3 of 15",
        next_label="Threshold Development",
        next_timing="Thursday",
        next_detail="5 × 1 km controlled",
    )


def _detail(athlete_id=1, *, primary=True, available=True):
    return GoalCoachDetail(
        athlete_id=athlete_id,
        hierarchy=_hierarchy(athlete_id, primary=primary),
        predictions=_predictions(athlete_id, available=available),
        home_summary=_summary(athlete_id),
    )


def test_goal_coach_page_makes_direction_capability_and_management_clear():
    markup = build_goal_coach_html(_detail())

    for expected in (
        "Goal Coach · Live direction",
        "Sub 39:00",
        "Leeds Abbey Dash",
        "38:13–39:53",
        "Central view <strong>39:03</strong>",
        "47%",
        "3s to find",
        "Threshold Coach",
        "Strongest signal",
        "Threshold",
        "Development focus",
        "Endurance",
        "Threshold Development",
        "Edit · Complete · Remove",
        "confirmed, reversible",
    ):
        assert expected in markup


def test_goal_coach_handles_an_athlete_without_a_primary_goal():
    markup = build_goal_coach_html(_detail(primary=False, available=False))

    assert "Choose a Primary goal" in markup
    assert "One direction for the whole coaching team" in markup
    assert "Waiting for a Primary goal" in markup
    assert "Current 10K capability" in markup


def test_goal_coach_composes_existing_services_without_a_new_formula(monkeypatch):
    hierarchy = _hierarchy(3)
    predictions = _predictions(3)
    summary = _summary(3)
    calls = {}

    monkeypatch.setattr(
        "core.goal_coach.build_goal_hierarchy",
        lambda athlete_id, reference_date=None: calls.setdefault(
            "hierarchy", (athlete_id, reference_date)
        ) and hierarchy,
    )
    monkeypatch.setattr(
        "core.goal_coach.build_home_predictions",
        lambda athlete_id: calls.setdefault("predictions", athlete_id) and predictions,
    )
    monkeypatch.setattr(
        "core.goal_coach.build_home_summary",
        lambda athlete_id, today=None: calls.setdefault(
            "summary", (athlete_id, today)
        ) and summary,
    )

    today = datetime.date(2026, 8, 26)
    detail = build_goal_coach_detail(3, today=today)

    assert detail.athlete_id == 3
    assert detail.hierarchy is hierarchy
    assert detail.predictions is predictions
    assert detail.home_summary is summary
    assert calls == {
        "hierarchy": (3, today),
        "predictions": 3,
        "summary": (3, today),
    }


def test_goal_removal_remains_confirmed_reversible_and_block_safe():
    source = (ROOT / "ui" / "goals.py").read_text(encoding="utf-8")
    core_source = (ROOT / "core" / "goals.py").read_text(encoding="utf-8")

    assert '"Remove goal"' in source
    assert '"Confirm removal"' in source
    assert '"Keep goal"' in source
    assert '"Restore as Future"' in source
    assert "safely archived" in source
    assert "status = 'Archived'" in core_source
    assert "no active training block or approved block design is" in core_source
    assert "deleted" in core_source


def test_training_coach_banner_contrast_is_explicitly_protected():
    source = (ROOT / "ui" / "next_run.py").read_text(encoding="utf-8")

    assert ".tc-hero h1" in source
    assert ".tc-next-key h2" in source
    assert source.count("color:#fff!important") >= 2
