from functools import lru_cache
from pathlib import Path

from core.passport_detail import build_passport_detail
from ui.passport import build_passport_html


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=2)
def _markup(athlete_id: int) -> str:
    return build_passport_html(build_passport_detail(athlete_id))


def test_passport_surface_uses_richard_real_evidence():
    markup = _markup(1)

    assert "Richard Burke" in markup
    assert "152 bpm" in markup
    assert "161 bpm" in markup
    assert "6:19/mi" in markup
    assert "6:10–6:15/mi cautious 12°C equivalent" in markup
    assert "Trail Warrior" in markup
    assert "47% more affected" in markup
    assert "35% less affected" in markup
    assert "103 TRUSTED WORKOUTS" in markup
    assert "31</b> high-confidence decoded threshold workouts" in markup
    assert "5</b> in the strict 12-month pace-trend set" in markup
    assert "2</b> with complete before/after response windows" in markup
    assert "1.8 mi" in markup
    assert "19:08" in markup
    assert "OFFICIAL TIMES ARE NEVER NORMALISED" in markup


def test_passport_surface_keeps_jo_independent_and_uncertainty_visible():
    richard = _markup(1)
    jo = _markup(3)

    assert "Joanne Burke" in jo
    assert "171 bpm" in jo
    assert "187 bpm" in jo
    assert "6:54/mi" in jo
    assert "Still emerging" in jo
    assert "Still learning" in jo
    assert "24 TRUSTED WORKOUTS" in jo
    assert "6:19/mi" not in jo
    assert richard != jo


def test_passport_training_profile_is_evidence_not_medical_zone_claim():
    markup = _markup(1)

    assert "TRAINING PROFILE" in markup
    assert "Recovery" in markup
    assert "Easy aerobic" in markup
    assert "Long Easy" in markup
    assert "Threshold" in markup
    assert "VO₂ development" in markup
    assert "Speed development" in markup
    assert "RPE-led" in markup
    assert "HR lags short work" in markup
    assert "historical patterns, not prescriptions" in markup
    assert "not presented as laboratory measurements" in markup
    assert "Typical distance" in markup
    assert "11.6 mi" in markup


def test_passport_route_and_responsive_contract():
    markup = _markup(1)
    app_source = (ROOT / "app.py").read_text()
    passport_source = (ROOT / "ui" / "passport.py").read_text()

    assert "from ui.passport import show_passport_page" in app_source
    assert 'elif page == "Passport":\n    show_passport_page()' in app_source
    assert "render_athlete_id_selector" in passport_source
    assert "container-type:inline-size" in markup
    assert "@container (max-width:1050px)" in markup
    assert "@container (max-width:760px)" in markup
    assert "@container (max-width:500px)" in markup
