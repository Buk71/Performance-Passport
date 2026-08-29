from __future__ import annotations

import datetime
from functools import lru_cache
from pathlib import Path

from core.learning_coach import LEARNING_LIBRARY, build_learning_coach_detail
from ui.learning import build_learning_coach_html, build_learning_library_html


ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.date(2026, 8, 29)


@lru_cache(maxsize=2)
def _detail(athlete_id: int):
    return build_learning_coach_detail(athlete_id, today=TODAY)


def test_learning_library_is_curated_broad_and_non_medical():
    assert len(LEARNING_LIBRARY) == 32
    assert len({item.key for item in LEARNING_LIBRARY}) == len(LEARNING_LIBRARY)
    assert len({item.topic for item in LEARNING_LIBRARY}) == 8
    assert all(item.coach and item.headline and item.explanation and item.action for item in LEARNING_LIBRARY)
    assert all("diagnos" not in item.explanation.lower() for item in LEARNING_LIBRARY)
    assert any(item.topic == "Understanding data" for item in LEARNING_LIBRARY)
    assert any(item.topic == "Fuel and hydration" for item in LEARNING_LIBRARY)


def test_learning_coach_composes_real_athlete_context_without_changing_training():
    detail = _detail(1)

    assert detail.athlete_id == 1
    assert detail.athlete_name == "Richard Burke"
    assert detail.profile.trusted_workout_count > 0
    assert detail.daily_lesson.insight in detail.library
    assert detail.daily_lesson.why_today
    assert len(detail.related_insights) == 3
    assert any("does not silently alter" in item for item in detail.limitations)
    assert any("observational" in item for item in detail.limitations)


def test_learning_coach_page_leads_with_today_and_preserves_personal_evidence():
    detail = _detail(1)
    markup = build_learning_coach_html(detail)

    assert "YOUR LEARNING COACH" in markup
    assert "TODAY’S LESSON" in markup
    assert "WHY IT IS RELEVANT" in markup
    assert "Personal associations from real training." in markup
    assert "Observational association · not proof of causation" in markup
    assert "Learning Coach guardrails" in markup
    assert ".learning-daily h2{color:#fff!important" in markup


def test_library_filter_and_performance_contracts_are_explicit():
    detail = _detail(1)
    recovery = build_learning_library_html(detail.library, topic="Recovery")
    source = (ROOT / "ui" / "learning.py").read_text(encoding="utf-8")
    composition = (ROOT / "core" / "learning_coach.py").read_text(encoding="utf-8")

    assert "4 LESSONS" in recovery
    assert "HRV is personal context, not a competition." in recovery
    assert "Race the opening kilometre with restraint." not in recovery
    assert "render_athlete_id_selector" in source
    assert "Load deeper personal learning evidence" in source
    assert "_cached_deep_evidence" in source
    assert "ThreadPoolExecutor" in composition
    assert 'thread_name_prefix="pp-learning"' in composition
