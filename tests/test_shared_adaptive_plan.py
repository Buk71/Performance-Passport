from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_live_integration_accepts_prepared_plan_with_fallback():
    source = (ROOT / "core" / "live_integration.py").read_text(encoding="utf-8")
    assert "prepared_plan: AdaptiveWeeklyPlan | None = None" in source
    assert "if prepared_plan is not None" in source
    assert "else build_adaptive_weekly_plan" in source


def test_arbitration_accepts_prepared_plan_and_proposal():
    source = (ROOT / "core" / "coaching_arbitration.py").read_text(encoding="utf-8")
    assert "prepared_plan: AdaptiveWeeklyPlan | None = None" in source
    assert "prepared_proposal: AdaptiveCoachProposal | None = None" in source
    assert "if prepared_proposal is not None" in source


def test_live_decision_builds_adaptive_plan_once_and_shares_it():
    source = (ROOT / "core" / "adaptive_coach_live.py").read_text(encoding="utf-8")
    body = source[source.index("def build_live_coach_decision("):]
    assert body.count("build_adaptive_weekly_plan(") == 1
    assert "prepared_plan=adaptive_plan" in body
    assert "prepared_proposal=proposal" in body


def test_existing_standalone_callers_remain_compatible():
    live = (ROOT / "core" / "live_integration.py").read_text(encoding="utf-8")
    arb = (ROOT / "core" / "coaching_arbitration.py").read_text(encoding="utf-8")
    assert "existing_label: str | None = None" in live
    assert "existing_recommendation: NextRunRecommendation | None = None" in arb
