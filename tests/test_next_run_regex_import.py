from pathlib import Path
import ast

SOURCE_PATH = Path(__file__).resolve().parent.parent / "ui" / "next_run.py"

def test_next_run_imports_re_for_distance_parser():
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "re" in imports

def test_distance_parser_uses_re_search():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "re.search(" in source
