from functools import lru_cache
from pathlib import Path

from core.progress import build_progress_summary
from ui.progress import build_progress_html


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=2)
def _markup(athlete_id: int) -> str:
    return build_progress_html(build_progress_summary(athlete_id))


def test_progress_surface_uses_richard_real_evidence():
    markup = _markup(1)

    assert "Aerobic fitness is moving forward" in markup
    assert "+4.4%" in markup
    assert "39.7" in markup
    assert "Mixed recent results" in markup
    assert "19:08" in markup
    assert "39:40" in markup
    assert "6:19/mi" in markup
    assert "Recent 6-month best" in markup
    assert "Previous 6-month best <strong>19:26</strong>" in markup
    assert "18s improvement" in markup
    assert "40s slower" in markup
    assert "18s faster" not in markup
    assert "40s softer" not in markup
    assert "6:10–6:15/mi" in markup
    assert "Estimated 12°C flat-road equivalent" in markup
    assert "cautious range, not a confirmed current threshold" in markup


def test_progress_surface_keeps_jo_independent():
    richard = _markup(1)
    jo = _markup(3)

    assert "+2.2%" in jo
    assert "27.5" in jo
    assert "22:51" in jo
    assert "47:29" in jo
    assert "6:54/mi" in jo
    assert "6:19/mi" not in jo
    assert richard != jo


def test_progress_surface_explains_adjustments_and_evidence_limits():
    markup = _markup(1)

    assert "CONDITIONS-NORMALISED" in markup
    assert "progress-aerobic-chart" in markup
    assert "<svg" not in markup
    assert "heat, humidity, climbing, wind and trail" in markup
    assert "Race progression" in markup
    assert "Rep/work-phase pace is used" in markup
    assert "interrupted Long Easy runs excluded" in markup
    assert "Treadmill time can support training rhythm" in markup
    assert "Long run" in markup
    assert "Sessions" in markup
    assert "progress-bar-segment is-quality" in markup
    assert "How Progress decides what counts" in markup


def test_progress_surface_is_sidebar_and_mobile_responsive():
    markup = _markup(1)

    assert "container-type:inline-size" in markup
    assert "@container (max-width:900px)" in markup
    assert "@container (max-width:650px)" in markup
    assert "@container (max-width:430px)" in markup
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in markup
    assert "overflow:hidden" in markup


def test_app_routes_progress_to_production_page_and_shares_selector():
    app_source = (ROOT / "app.py").read_text()
    home_source = (ROOT / "ui" / "home.py").read_text()
    progress_source = (ROOT / "ui" / "progress.py").read_text()
    selection_source = (ROOT / "ui" / "athlete_selection.py").read_text()

    assert "from ui.progress import show_progress_page" in app_source
    assert 'elif page == "Progress":\n    show_progress_page()' in app_source
    assert "render_athlete_id_selector" in home_source
    assert "render_athlete_id_selector" in progress_source
    assert "key=SESSION_ID_KEY" in selection_source
