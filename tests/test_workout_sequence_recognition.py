import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_workout_provider_preserves_order_and_uses_decoder_v5():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")

    assert "WORKOUT_LIBRARY_DECODER_VERSION = 5" in source
    assert "splits = list(_work_splits(workout))" in source
    assert "structure_shape" in source
    assert "distance_sequence_m" in source


def test_pyramid_signature_is_sequence_specific():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")

    assert 'return f"{shape}_"' in source
    assert '"pyramid"' in source
    assert '"ascending_ladder"' in source
    assert '"descending_ladder"' in source


def test_real_garmin_10708_pyramid_is_recognised_without_title():
    from core.workout_title_intent import (
        build_fit_structure_evidence,
        infer_fit_workout_structure,
    )

    raw = {"fit_splits": [{'index': 1, 'distance_km': 0.08941, 'duration_s': 30.018, 'elapsed_time_s': 56.164, 'lap_trigger': 'manual'}, {'index': 2, 'distance_km': 0.09712, 'duration_s': 19.331, 'elapsed_time_s': 19.331, 'lap_trigger': 'manual'}, {'index': 3, 'distance_km': 0.01218, 'duration_s': 3.643, 'elapsed_time_s': 83.03, 'lap_trigger': 'manual'}, {'index': 4, 'distance_km': 0.09079, 'duration_s': 16.569, 'elapsed_time_s': 16.569, 'lap_trigger': 'manual'}, {'index': 5, 'distance_km': 0.01371, 'duration_s': 3.425, 'elapsed_time_s': 82.907, 'lap_trigger': 'manual'}, {'index': 6, 'distance_km': 0.09478, 'duration_s': 16.721, 'elapsed_time_s': 16.721, 'lap_trigger': 'manual'}, {'index': 7, 'distance_km': 0.01627, 'duration_s': 4.462, 'elapsed_time_s': 91.864, 'lap_trigger': 'manual'}, {'index': 8, 'distance_km': 0.0962, 'duration_s': 17.491, 'elapsed_time_s': 17.491, 'lap_trigger': 'manual'}, {'index': 9, 'distance_km': 0.01198, 'duration_s': 3.949, 'elapsed_time_s': 166.764, 'lap_trigger': 'manual'}, {'index': 10, 'distance_km': 0.39756, 'duration_s': 84.888, 'elapsed_time_s': 84.888, 'lap_trigger': 'manual'}, {'index': 11, 'distance_km': 0.01117, 'duration_s': 3.872, 'elapsed_time_s': 62.572, 'lap_trigger': 'manual'}, {'index': 12, 'distance_km': 0.79115, 'duration_s': 185.251, 'elapsed_time_s': 185.251, 'lap_trigger': 'manual'}, {'index': 13, 'distance_km': 0.01158, 'duration_s': 4.041, 'elapsed_time_s': 75.885, 'lap_trigger': 'manual'}, {'index': 14, 'distance_km': 1.18656, 'duration_s': 281.888, 'elapsed_time_s': 281.888, 'lap_trigger': 'manual'}, {'index': 15, 'distance_km': 0.01015, 'duration_s': 3.818, 'elapsed_time_s': 76.29, 'lap_trigger': 'manual'}, {'index': 16, 'distance_km': 1.59266, 'duration_s': 384.004, 'elapsed_time_s': 384.004, 'lap_trigger': 'manual'}, {'index': 17, 'distance_km': 0.01146, 'duration_s': 4.35, 'elapsed_time_s': 66.334, 'lap_trigger': 'manual'}, {'index': 18, 'distance_km': 1.60934, 'duration_s': 392.785, 'elapsed_time_s': 392.785, 'lap_trigger': 'distance'}, {'index': 19, 'distance_km': 0.37855, 'duration_s': 92.231, 'elapsed_time_s': 92.231, 'lap_trigger': 'manual'}, {'index': 20, 'distance_km': 0.01239, 'duration_s': 3.94, 'elapsed_time_s': 72.694, 'lap_trigger': 'manual'}, {'index': 21, 'distance_km': 1.58688, 'duration_s': 380.869, 'elapsed_time_s': 380.869, 'lap_trigger': 'manual'}, {'index': 22, 'distance_km': 0.01241, 'duration_s': 3.578, 'elapsed_time_s': 77.938, 'lap_trigger': 'manual'}, {'index': 23, 'distance_km': 1.19264, 'duration_s': 279.834, 'elapsed_time_s': 279.834, 'lap_trigger': 'manual'}, {'index': 24, 'distance_km': 0.01244, 'duration_s': 4.134, 'elapsed_time_s': 73.36, 'lap_trigger': 'manual'}, {'index': 25, 'distance_km': 0.79353, 'duration_s': 176.974, 'elapsed_time_s': 176.974, 'lap_trigger': 'manual'}, {'index': 26, 'distance_km': 0.0113, 'duration_s': 3.872, 'elapsed_time_s': 70.192, 'lap_trigger': 'manual'}, {'index': 27, 'distance_km': 0.39893, 'duration_s': 74.585, 'elapsed_time_s': 74.585, 'lap_trigger': 'manual'}, {'index': 28, 'distance_km': 0.01074, 'duration_s': 3.986, 'elapsed_time_s': 278.169, 'lap_trigger': 'manual'}, {'index': 29, 'distance_km': 0.08128, 'duration_s': 17.952, 'elapsed_time_s': 17.952, 'lap_trigger': 'manual'}, {'index': 30, 'distance_km': 0.00728, 'duration_s': 2.997, 'elapsed_time_s': 85.888, 'lap_trigger': 'manual'}, {'index': 31, 'distance_km': 0.08454, 'duration_s': 18.118, 'elapsed_time_s': 18.118, 'lap_trigger': 'manual'}, {'index': 32, 'distance_km': 0.01128, 'duration_s': 3.996, 'elapsed_time_s': 89.655, 'lap_trigger': 'manual'}, {'index': 33, 'distance_km': 0.08524, 'duration_s': 19.072, 'elapsed_time_s': 19.072, 'lap_trigger': 'manual'}, {'index': 34, 'distance_km': 0.0076, 'duration_s': 3.007, 'elapsed_time_s': 80.871, 'lap_trigger': 'manual'}, {'index': 35, 'distance_km': 0.07934, 'duration_s': 16.555, 'elapsed_time_s': 16.555, 'lap_trigger': 'manual'}, {'index': 36, 'distance_km': 0.00729, 'duration_s': 1.299, 'elapsed_time_s': 1.299, 'lap_trigger': 'session_end'}]}
    payload = json.dumps(raw)
    intent = infer_fit_workout_structure(payload)

    assert intent is not None
    assert intent.structure_shape == "pyramid"
    assert intent.total_reps == 9
    assert [round(value * 1000) for value in intent.distance_sequence_km] == [
        400, 800, 1200, 1600, 2000, 1600, 1200, 800, 400
    ]
    assert 60 <= intent.recovery_s <= 80
    assert intent.confidence >= 0.95

    evidence = build_fit_structure_evidence(payload)
    assert evidence is not None
    assert evidence["metadata"]["source"] == "garmin_fit_ordered_laps"
    assert evidence["metadata"]["total_reps"] == 9
    assert evidence["metadata"]["nominal_work_distance_km"] == 10.0
    assert 9.90 <= evidence["metadata"]["total_work_distance_km"] <= 9.95

    two_k = evidence["metadata"]["phases"][4]
    assert two_k["average_rep_distance_km"] == 2.0
    assert two_k["split_indexes"] == [18, 19]
    assert two_k["metadata"]["segment_count"] == 2


def test_fit_structure_does_not_promote_continuous_autolaps():
    from core.workout_title_intent import infer_fit_workout_structure

    raw = {
        "fit_splits": [
            {
                "index": index,
                "distance_km": 1.60934,
                "duration_s": 430.0,
                "elapsed_time_s": 430.0,
                "lap_trigger": "distance",
            }
            for index in range(1, 9)
        ]
    }

    assert infer_fit_workout_structure(json.dumps(raw)) is None


def test_activity_review_uses_title_or_fit_canonical_structure():
    source = (ROOT / "core" / "activity_review.py").read_text(encoding="utf-8")
    assert "build_workout_structure_evidence" in source
    assert "inferred_structure" in source
