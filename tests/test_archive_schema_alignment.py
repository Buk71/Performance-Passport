from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent.parent


def _sql_strings_in_function(filename: str, function_name: str) -> list[str]:
    source = (ROOT / "core" / filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            sql_strings = []
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    text = child.value
                    if "SELECT" in text.upper():
                        sql_strings.append(text)
            return sql_strings
    raise AssertionError(f"{function_name} not found")


def test_archive_intelligence_uses_real_activity_schema_columns():
    source = (ROOT / "core" / "archive_intelligence.py").read_text(encoding="utf-8")

    assert "sport_id" in source
    assert "distance_m" in source
    assert "moving_time_s" in source
    assert "elapsed_time_s" in source

    sql = "\n".join(
        _sql_strings_in_function(
            "archive_intelligence.py",
            "build_archive_history_summary",
        )
    )

    # The production SQL must use the real activities-table columns.
    assert "distance_m" in sql
    assert "moving_time_s" in sql
    assert "elapsed_time_s" in sql

    # Generic/nonexistent schema column names must not appear in SQL.
    assert "distance_km" not in sql
    assert "duration_s" not in sql
    assert "LOWER(COALESCE(sport" not in sql


def test_running_count_uses_athlete_sport_mapping():
    source = (ROOT / "core" / "archive_intelligence.py").read_text(encoding="utf-8")
    assert "get_athlete_sport_roles" in source
    assert 'if str(role).lower() == "running"' in source
