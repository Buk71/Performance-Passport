from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent.parent


def _source():
    return (
        ROOT / "core" / "performance_backtracking.py"
    ).read_text(encoding="utf-8")


def test_backtracking_has_source_aware_process_cache():
    source = _source()
    assert "from functools import lru_cache" in source
    assert "get_training_intelligence_version" in source
    assert "def _backtracking_source_version(" in source
    assert "@lru_cache(maxsize=64)" in source
    assert "def _build_performance_backtracking_profile_cached(" in source


def test_backtracking_version_includes_workout_library_state():
    source = _source()
    assert "FROM workout_library" in source
    assert "COUNT(*)" in source
    assert "MAX(updated_at)" in source


def test_public_builder_signature_remains_compatible():
    tree = ast.parse(_source())
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_performance_backtracking_profile"
    )
    args = [arg.arg for arg in target.args.args]
    assert args == ["athlete_id"]


def test_uncached_builder_is_preserved():
    source = _source()
    assert "def _build_performance_backtracking_profile_uncached(" in source
    assert "return _build_performance_backtracking_profile_uncached(" in source
