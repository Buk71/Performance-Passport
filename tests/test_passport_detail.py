import datetime

from core.passport_detail import build_passport_detail


REFERENCE_DATE = datetime.date(2026, 8, 9)


def test_richard_passport_composes_real_current_evidence():
    detail = build_passport_detail(1, reference_date=REFERENCE_DATE)

    assert detail is not None
    assert detail.athlete.full_name == "Richard Burke"
    assert detail.confidence == "Strong"
    assert detail.available_training_profiles == 6
    assert detail.trusted_workout_count == 103
    assert detail.threshold_source == "Athlete profile values"
    assert [(item.key, item.value) for item in detail.anchors] == [
        ("lt1", "152 bpm"),
        ("lt2", "161 bpm"),
        ("threshold", "6:19/mi"),
        ("aerobic", "+4.4%"),
        ("durability", "3.4%"),
    ]
    assert detail.performance_trait is not None
    assert detail.performance_trait.title == "Trail Warrior"
    assert detail.threshold_evidence.decoded_workout_count == 31
    assert detail.threshold_evidence.strict_progress_count == 5
    assert detail.threshold_evidence.response_window_count == 2
    threshold_distance = detail.threshold_evidence.typical_work_distance_km
    assert threshold_distance is not None
    assert 2.0 <= threshold_distance <= 4.0
    responses = {item.key: item for item in detail.environment}
    assert responses["heat"].response_label == "47% more affected"
    assert responses["trail"].response_label == "35% less affected"


def test_jo_passport_remains_independent():
    detail = build_passport_detail(3, reference_date=REFERENCE_DATE)

    assert detail is not None
    assert detail.athlete.full_name == "Joanne Burke"
    assert detail.available_training_profiles == 5
    assert detail.trusted_workout_count == 23
    assert [(item.key, item.value) for item in detail.anchors[:3]] == [
        ("lt1", "171 bpm"),
        ("lt2", "187 bpm"),
        ("threshold", "6:54/mi"),
    ]
    assert detail.performance_trait is None
    assert detail.threshold_evidence.decoded_workout_count == 4
    assert detail.threshold_evidence.strict_progress_count == 2
    assert detail.threshold_evidence.response_window_count == 0
    responses = {item.key: item for item in detail.environment}
    assert responses["heat"].response_label == "60% more affected"
    assert responses["trail"].response_label == "Still learning"


def test_passport_training_profile_reuses_blueprint_safeguards():
    richard = build_passport_detail(1, reference_date=REFERENCE_DATE)

    assert richard.training.easy.show_pace is True
    assert richard.training.threshold.show_pace is False
    assert richard.training.threshold.hr_typical == 156
    assert richard.training.vo2.rep_metric_sample_size == 4
    assert richard.training.speed.rep_metric_sample_size == 85
    assert richard.training.recovery.typical_distance_km == 6.1
    assert richard.training.long_easy.typical_distance_km == 18.6
    assert any("not mandatory pace limits" in note for note in richard.evidence_notes)
    assert any("Heart rate is not used as the primary guide" in note for note in richard.evidence_notes)
