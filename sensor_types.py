"""Shared sensor reading types used by hardware and demo data sources."""

from dataclasses import dataclass
import math


@dataclass
class SensorReading:
    """Single sensor reading and its validity/freshness metadata."""

    obstacle_distance_m: float | None
    speed_kmh: float | None
    timestamp: float
    source: str
    valid: bool
    stale: bool = False
    error: str | None = None


def sensor_data_status(reading: SensorReading) -> str:
    """Return availability state without treating stale or invalid values as current."""
    values = (reading.obstacle_distance_m, reading.speed_kmh)
    if (
        not reading.valid
        or reading.stale
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in values
        )
    ):
        return "SENSOR DATA UNAVAILABLE"
    return "AVAILABLE"
