from ui.threshold_display import threshold_source

def test_profile_does_not_claim_automatic_or_verified():
    row = {"override_enabled": False, "calculated_lt2_hr": 161, "estimated_lt2_hr": 159}
    result = threshold_source(row, "lt2")
    assert "Stored athlete profile" in result
    assert "original source not recorded" in result

def test_manual_source_is_explicit():
    row = {"override_enabled": True, "manual_lt1_hr": 152, "override_source": "Field test"}
    assert "Field test" in threshold_source(row, "lt1")

def test_automatic_fallback():
    row = {"override_enabled": False, "calculated_max_hr": None, "estimated_max_hr": 170}
    assert "Automatically estimated" in threshold_source(row, "max")


def test_settings_imports_only_available_threshold_helpers():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "ui" / "settings.py").read_text()
    assert "from ui.threshold_display import threshold_source" in source
    assert "source_explanation" not in source
