from core.beginner_sessions import build_couch_to_5k_session
from core.session import BlockType, SessionPurpose, SessionType

def test_walk_foundation_is_walking():
    s = build_couch_to_5k_session("walking_foundation")
    assert s.session_type == SessionType.WALK
    assert s.purpose == SessionPurpose.EASY

def test_short_run_walk_has_no_pace_target():
    s = build_couch_to_5k_session("run_walk_short")
    assert "no pace target" in s.pace_guidance.lower()
    assert any(b.block_type == BlockType.WORK for b in s.blocks)
    assert any(b.block_type == BlockType.RECOVERY for b in s.blocks)

def test_5_minute_stage_is_four_blocks():
    s = build_couch_to_5k_session("run_blocks_5")
    w = [b for b in s.blocks if b.block_type == BlockType.WORK][0]
    assert (w.duration_s, w.repeat_count) == (300, 4)

def test_8_minute_stage_is_three_blocks():
    s = build_couch_to_5k_session("run_blocks_8")
    w = [b for b in s.blocks if b.block_type == BlockType.WORK][0]
    assert (w.duration_s, w.repeat_count) == (480, 3)

def test_10_minute_stage_is_two_blocks():
    s = build_couch_to_5k_session("run_blocks_10")
    w = [b for b in s.blocks if b.block_type == BlockType.WORK][0]
    assert (w.duration_s, w.repeat_count) == (600, 2)

def test_continuous_20_uses_continuous_run():
    s = build_couch_to_5k_session("continuous_20")
    assert s.session_type == SessionType.CONTINUOUS_RUN
    c = [b for b in s.blocks if b.block_type == BlockType.CONTINUOUS][0]
    assert c.duration_s == 1200

def test_continuous_30_is_easy():
    s = build_couch_to_5k_session("continuous_30")
    assert s.purpose == SessionPurpose.EASY

def test_all_stages_collect_core_feedback():
    stages = ("walking_foundation","run_walk_short","run_walk_build","run_blocks_5",
              "run_blocks_8","run_blocks_10","continuous_15","continuous_20",
              "continuous_25","continuous_30","5k_ready")
    for stage in stages:
        text = " ".join(build_couch_to_5k_session(stage).collect_after).lower()
        assert "complete" in text and "difficult" in text and "pain" in text

def test_unknown_stage_fails():
    try:
        build_couch_to_5k_session("week_99")
    except ValueError:
        pass
    else:
        raise AssertionError("Unsupported stage should raise ValueError")
