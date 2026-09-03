from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent.parent


def _function_body(filename: str, function_name: str) -> str:
    source = (ROOT / "core" / filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr):
                value = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    body = body[1:]
            return "\n".join(ast.unparse(item) for item in body)
    raise AssertionError(f"{function_name} not found")


def test_training_version_contains_training_sources_but_not_derived_tables():
    body = _function_body("cache_version.py", "get_training_intelligence_version")

    for source in (
        "activities",
        "athlete_health_daily",
        "goals",
        "training_blocks",
        "training_block_designs",
        "block_review_actions",
        "athlete_recovery_checkins",
        "athlete_activity_overrides",
        "athlete_threshold_overrides",
    ):
        assert source in body

    assert "workout_library" not in body
    assert "nutrition_week_selections" not in body


def test_training_coach_uses_persistent_typed_intelligence():
    source = (ROOT / "core" / "training_coach.py").read_text(encoding="utf-8")

    assert "_build_training_coach_detail_uncached" in source
    assert "get_training_intelligence_version" in source
    assert "get_or_build_typed_intelligence" in source
    assert 'training.coach_detail.v1.' in source


def test_training_coach_key_is_calendar_day_specific():
    source = (ROOT / "core" / "training_coach.py").read_text(encoding="utf-8")
    assert "effective_today.isoformat()" in source
