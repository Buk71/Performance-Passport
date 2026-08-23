from pathlib import Path

from ui.athlete_card import _athlete_photo_path, image_to_data_uri


ROOT = Path(__file__).resolve().parent.parent


def test_paul_farrell_has_his_own_real_passport_photo():
    path = _athlete_photo_path("Paul", "Farrell")

    assert path == ROOT / "assets" / "athletes" / "paul_farrell.jpg"
    assert path.exists()
    assert path.stat().st_size > 300_000
    assert image_to_data_uri(path).startswith("data:image/jpeg;base64,")


def test_paul_photo_has_a_specific_finish_line_crop():
    source = (ROOT / "ui" / "athlete_card.py").read_text(encoding="utf-8")

    assert "pp-photo-{photo_key}" in source
    assert ".pp-photo-paul_farrell" in source
    assert "object-position: 48% 40%" in source
    assert "object-position: 48% 36%" in source
