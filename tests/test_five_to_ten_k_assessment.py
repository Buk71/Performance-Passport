import datetime
from unittest.mock import patch
from core.five_to_ten_k_assessment import _distance_km, build_five_to_ten_k_assessment

class _Conn:
    def __init__(self, rows): self.rows = rows
    def execute(self, *_a, **_k): return self
    def fetchall(self): return self.rows
    def close(self): pass

def test_distance_handles_km_and_metres():
    assert _distance_km(5.1) == 5.1
    assert _distance_km(10000) == 10.0

def test_recent_5k_allows_pathway():
    rows = [
        ("2026-09-01", 5.0, "running", "", "Easy Run"),
        ("2026-09-03", 6.0, "running", "", "Long Run"),
    ]
    with patch("core.five_to_ten_k_assessment.get_connection", return_value=_Conn(rows)):
        assessment, evidence = build_five_to_ten_k_assessment(
            1, sessions_per_week=3, today=datetime.date(2026,9,5)
        )
    assert assessment.can_complete_5k is True
    assert evidence.longest_recent_run_km == 6.0

def test_no_recent_5k_blocks_pathway():
    rows = [("2026-09-01", 4.5, "running", "", "Easy Run")]
    with patch("core.five_to_ten_k_assessment.get_connection", return_value=_Conn(rows)):
        assessment, _ = build_five_to_ten_k_assessment(
            1, sessions_per_week=3, today=datetime.date(2026,9,5)
        )
    assert assessment.can_complete_5k is False
