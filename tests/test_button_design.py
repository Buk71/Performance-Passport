from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_global_buttons_use_readable_secondary_surface():
    source = (ROOT / "theme.py").read_text()

    assert ".stFormSubmitButton > button" in source
    assert "color: #10263D" in source
    assert "background: #FFFFFF" in source
    assert "border: 1px solid #D7D0C6" in source
    assert "background: var(--pp-accent);\n            border: 0" not in source


def test_primary_buttons_use_ink_with_white_text():
    source = (ROOT / "theme.py").read_text()

    assert 'button[kind="primary"]' in source
    assert '[data-testid="stBaseButton-primary"]' in source
    assert "color: #FFFFFF" in source
    assert "background: #10263D" in source
    assert "background: #193B59" in source


def test_buttons_keep_visible_keyboard_focus_and_disabled_states():
    source = (ROOT / "theme.py").read_text()

    assert "button:focus-visible" in source
    assert "rgba(241, 90, 36, 0.18)" in source
    assert "button:disabled" in source


def test_feature_pages_apply_the_action_hierarchy_deliberately():
    goals = (ROOT / "ui" / "goals.py").read_text()
    predictor = (ROOT / "ui" / "race_outlook.py").read_text()
    blocks = (ROOT / "ui" / "training_blocks.py").read_text()

    assert 'button("Make Primary"' in goals
    assert 'type="primary"' in goals
    assert 'form_submit_button("Save goal", type="primary")' in goals
    assert 'st.markdown("#### 2. Quick-start scenarios")' in predictor
    assert "column.button(" in predictor
    assert 'type="primary"' not in predictor
    assert 'st.button(button_label, type="primary"' in blocks
