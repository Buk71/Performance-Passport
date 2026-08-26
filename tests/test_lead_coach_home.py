import datetime
from functools import lru_cache
from pathlib import Path

from core.athlete_passport import build_athlete_passport
from core.home_latest_run import build_home_latest_run
from core.home_prediction_matrix import build_home_prediction_matrix
from core.home_predictions import build_home_predictions
from core.home_summary import build_home_summary
from ui.lead_coach_home import build_lead_coach_home_html


ROOT = Path(__file__).resolve().parent.parent
RENDER_DATE = datetime.date(2026, 8, 26)


@lru_cache(maxsize=3)
def _real_home(athlete_id):
    return (
        build_athlete_passport(athlete_id),
        build_home_summary(athlete_id, today=RENDER_DATE),
        build_home_predictions(athlete_id),
        build_home_latest_run(athlete_id),
    )


def test_lead_coach_home_uses_real_independent_athlete_services():
    expected_names = {
        1: "Richard Burke",
        3: "Joanne Burke",
        4: "Paul Farrell",
    }
    rendered = {}

    for athlete_id, expected_name in expected_names.items():
        passport, summary, predictions, latest = _real_home(athlete_id)
        markup = build_lead_coach_home_html(
            athlete_id,
            passport,
            summary,
            predictions,
            latest,
            today=RENDER_DATE,
        )
        rendered[athlete_id] = markup

        assert expected_name in markup
        assert summary.goal_name in markup
        assert predictions.distance_label in markup
        assert "Lead Coach briefing" in markup
        assert "Your coaching team" in markup
        assert "Race Coach outlook" in markup
        assert "Four distances · six race environments" in markup
        assert "Ballpark capability view" in markup
        assert all(
            label in markup
            for label in ("5K", "10K", "Half", "Marathon")
        )
        assert len(summary.week_days) == 7
        assert all(day.day_name[:3] in markup for day in summary.week_days)
        assert all(
            coach.title in markup
            for coach in predictions.coach_positions
        )
        assert all(
            scenario.label in markup
            for scenario in predictions.scenarios
        )

    assert rendered[1] != rendered[3]
    assert rendered[3] != rendered[4]
    assert "Paul Farrell" not in rendered[1]
    assert "Joanne Burke" not in rendered[4]


def test_lead_coach_home_keeps_mock_values_out_of_production_markup():
    passport, summary, predictions, latest = _real_home(1)
    markup = build_lead_coach_home_html(
        1,
        passport,
        summary,
        predictions,
        latest,
        today=RENDER_DATE,
    )

    assert "illustrative" not in markup.lower()
    assert "mock" not in markup.lower()
    assert "1.06 equivalence rule" in markup.lower()
    assert "build_home_predictions" not in markup


def test_production_home_delegates_to_lead_coach_experience():
    source = (ROOT / "ui" / "home.py").read_text()

    assert "from ui.lead_coach_home import show_lead_coach_home_page" in source
    assert '"""Render the premium Lead Coach Home using real athlete data."""' in source
    assert "show_lead_coach_home_page()" in source


def test_lead_coach_home_has_responsive_premium_layout():
    source = (ROOT / "ui" / "lead_coach_home.py").read_text()

    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in source
    assert "grid-template-columns:repeat(7,minmax(0,1fr))" in source
    assert "@media (max-width:1180px)" in source
    assert "@media (max-width:760px)" in source
    assert "Four distances · six race environments" in source


def test_prediction_matrix_is_a_consistent_real_capability_translation():
    for athlete_id in (1, 3, 4):
        predictions = _real_home(athlete_id)[2]
        matrix = build_home_prediction_matrix(predictions)

        assert matrix.available is True
        assert matrix.athlete_id == athlete_id
        assert [row.label for row in matrix.rows] == [
            "5K", "10K", "Half", "Marathon",
        ]
        assert all(len(row.cells) == 6 for row in matrix.rows)
        assert [cell.label for cell in matrix.rows[0].cells] == [
            "Ideal", "Typical UK", "Warm", "Hilly", "Windy", "Trail",
        ]
        assert sum(row.is_active_distance for row in matrix.rows) == 1

        active = next(row for row in matrix.rows if row.is_active_distance)
        ideal = next(cell for cell in active.cells if cell.key == "ideal")
        assert ideal.seconds == predictions.central_seconds

        ideal_times = [
            next(cell.seconds for cell in row.cells if cell.key == "ideal")
            for row in matrix.rows
        ]
        assert ideal_times == sorted(ideal_times)
        assert all(
            next(cell.seconds for cell in row.cells if cell.key == "trail")
            > next(cell.seconds for cell in row.cells if cell.key == "ideal")
            for row in matrix.rows
        )
