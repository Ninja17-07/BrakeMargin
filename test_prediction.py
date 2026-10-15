import pytest

from prediction import compute_all
from sensor_types import SensorReading, sensor_data_status


@pytest.mark.parametrize(
    ("distance_m", "expected_status"),
    [
        (0.20, "DANGER"),
        (0.21, "CAUTION"),
        (0.70, "CAUTION"),
        (0.71, "SAFE"),
    ],
)
def test_risk_status_uses_exact_obstacle_distance_boundaries(
    distance_m, expected_status
):
    assert compute_all(obstacle_distance_m=distance_m, speed_kmh=60.0)["status"] == expected_status


def test_invalid_or_stale_readings_are_unavailable():
    invalid = SensorReading(None, None, 0.0, "hardware", False, error="invalid message")
    stale = SensorReading(10.0, 20.0, 0.0, "hardware", False, stale=True)

    assert sensor_data_status(invalid) == "SENSOR DATA UNAVAILABLE"
    assert sensor_data_status(stale) == "SENSOR DATA UNAVAILABLE"


def test_disconnected_reading_is_unavailable():
    disconnected = SensorReading(
        None,
        None,
        0.0,
        "hardware",
        False,
        error="Serial port is disconnected.",
    )

    assert sensor_data_status(disconnected) == "SENSOR DATA UNAVAILABLE"


def test_high_speed_does_not_override_distance_based_safe_status():
    reading = compute_all(obstacle_distance_m=5.0, speed_kmh=160.0)

    assert reading["status"] == "SAFE"
    assert reading["safety_margin_m"] < 0


def test_braking_metrics_are_independent_of_obstacle_distance():
    close = compute_all(obstacle_distance_m=0.5, speed_kmh=60.0)
    far = compute_all(obstacle_distance_m=5.0, speed_kmh=60.0)

    assert close["reaction_distance_m"] == far["reaction_distance_m"]
    assert close["braking_distance_m"] == far["braking_distance_m"]
    assert close["stopping_distance_m"] == far["stopping_distance_m"]
    assert close["safety_margin_m"] != far["safety_margin_m"]
