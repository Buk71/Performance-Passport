from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent.parent


def _function_source(filename: str, function_name: str) -> str:
    path = ROOT / "core" / filename
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            # Only inspect executable statements, not the function docstring.
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr):
                value = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    body = body[1:]
            return "\n".join(ast.unparse(statement) for statement in body)
    raise AssertionError(f"{function_name} not found in {filename}")


def test_race_source_version_excludes_derived_workout_library():
    race_body = _function_source("cache_version.py", "get_race_intelligence_version")

    assert "athlete_activity_overrides" in race_body
    assert "athlete_personal_best_overrides" in race_body
    assert "athlete_threshold_overrides" in race_body
    assert "athlete_sport_mappings" in race_body

    assert "workout_library" not in race_body
    assert "nutrition_week_selections" not in race_body
    assert "athlete_recovery_checkins" not in race_body


def test_all_materialised_race_builders_use_race_specific_version():
    for filename in (
        "home_predictions.py",
        "distance_prediction_outlook.py",
        "race_coach.py",
    ):
        source = (ROOT / "core" / filename).read_text(encoding="utf-8")
        assert "get_race_intelligence_version" in source
        assert "get_athlete_cache_version" not in source


def test_goal_remains_part_of_materialised_key():
    home = (ROOT / "core" / "home_predictions.py").read_text(encoding="utf-8")
    race = (ROOT / "core" / "race_coach.py").read_text(encoding="utf-8")

    assert "stable_key_fragment(goal or {})" in home
    assert "stable_key_fragment(goal or {})" in race
