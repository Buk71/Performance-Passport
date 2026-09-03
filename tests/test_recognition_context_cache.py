from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent.parent


def _source():
    return (
        ROOT / "core" / "performance_recognition.py"
    ).read_text(encoding="utf-8")


def test_activity_context_cache_is_source_version_aware():
    source = _source()
    assert "from functools import lru_cache" in source
    assert "get_training_intelligence_version" in source
    assert "@lru_cache(maxsize=64)" in source
    assert "def _activity_context_lookup_cached(" in source
    assert "source_version = tuple(" in source


def test_public_internal_lookup_signature_remains_compatible():
    tree = ast.parse(_source())
    target = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_activity_context_lookup"
    )

    positional = [
        arg.arg
        for arg in (
            list(target.args.posonlyargs)
            + list(target.args.args)
        )
    ]
    assert positional == ["athlete_id"]
    assert target.args.vararg is None
    assert target.args.kwarg is None


def test_recognition_index_still_uses_context_lookup():
    source = _source()
    build_pos = source.index("def build_recognition_index(")
    body = source[build_pos:]
    assert "context_lookup = _activity_context_lookup(athlete_id)" in body
