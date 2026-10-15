
"""
BrakeMargin - Predictive Braking Safety Calculations

Estimates stopping distance and safety margin using configurable assumptions.
These estimates are for prototype demonstrations, not guaranteed stopping distances
or real-world motorcycle safety decisions.
"""

from dataclasses import dataclass


# ============================================================
# DEFAULT ASSUMPTIONS — ALIGNED WITH THE ESP32 DEMO
# ============================================================

DEFAULT_REACTION_TIME_S = 1.5
DEFAULT_BRAKING_DECELERATION_MPS2 = 5.0
DEFAULT_SAFETY_BUFFER_M = 0.0

KM_H_TO_M_S = 1.0 / 3.6

# Legacy safety-margin thresholds; dashboard risk classification uses the
# obstacle-distance thresholds below.
DEFAULT_SAFE_THRESHOLD_M = 2.0
DEFAULT_CAUTION_THRESHOLD_M = 0.0
DEFAULT_DANGER_DISTANCE_M = 0.20
DEFAULT_CAUTION_DISTANCE_M = 0.70


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass(frozen=True)
class PredictionConfig:
    """Configuration for the prediction engine."""

    reaction_time_s: float = DEFAULT_REACTION_TIME_S
    braking_deceleration_mps2: float = (
        DEFAULT_BRAKING_DECELERATION_MPS2
    )
    safety_buffer_m: float = DEFAULT_SAFETY_BUFFER_M
    safe_threshold_m: float = DEFAULT_SAFE_THRESHOLD_M
    caution_threshold_m: float = DEFAULT_CAUTION_THRESHOLD_M

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.reaction_time_s < 0:
            raise ValueError("reaction_time_s must be non-negative")

        if self.braking_deceleration_mps2 <= 0:
            raise ValueError(
                "braking_deceleration_mps2 must be positive"
            )

        if self.safety_buffer_m < 0:
            raise ValueError("safety_buffer_m must be non-negative")

        if self.safe_threshold_m <= self.caution_threshold_m:
            raise ValueError(
                "safe_threshold_m must be greater than "
                "caution_threshold_m"
            )


@dataclass(frozen=True)
class PredictionResult:
    """Result of a braking safety prediction."""

    stopping_distance_m: float
    safety_margin_m: float
    status: str
    explanation: str
    reaction_distance_m: float
    braking_distance_m: float
    speed_ms: float


class PredictionError(ValueError):
    """Raised when prediction inputs are invalid."""


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs(
    speed_kmh: float,
    obstacle_distance_m: float,
    reaction_time_s: float,
    braking_deceleration_mps2: float,
    safety_buffer_m: float,
) -> None:
    """Validate inputs and raise PredictionError if invalid."""

    values = {
        "speed_kmh": speed_kmh,
        "obstacle_distance_m": obstacle_distance_m,
        "reaction_time_s": reaction_time_s,
        "braking_deceleration_mps2": braking_deceleration_mps2,
        "safety_buffer_m": safety_buffer_m,
    }

    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PredictionError(f"{name} must be a number")

        if not float("-inf") < value < float("inf"):
            raise PredictionError(f"{name} must be finite")

    if speed_kmh < 0:
        raise PredictionError("speed_kmh must be non-negative")

    if obstacle_distance_m < 0:
        raise PredictionError(
            "obstacle_distance_m must be non-negative"
        )

    if reaction_time_s < 0:
        raise PredictionError(
            "reaction_time_s must be non-negative"
        )

    if braking_deceleration_mps2 <= 0:
        raise PredictionError(
            "braking_deceleration_mps2 must be positive"
        )

    if safety_buffer_m < 0:
        raise PredictionError(
            "safety_buffer_m must be non-negative"
        )


# ============================================================
# CORE CALCULATIONS
# ============================================================

def speed_kmh_to_ms(speed_kmh: float) -> float:
    """Convert speed from km/h to m/s."""
    return speed_kmh * KM_H_TO_M_S


def compute_stopping_distance(
    speed_kmh: float,
    reaction_time_s: float,
    braking_deceleration_mps2: float,
) -> tuple[float, float, float]:
    """
    Calculate estimated stopping distance.

    Reaction distance = speed in m/s * reaction time
    Braking distance = speed in m/s squared / (2 * deceleration)

    Returns:
        (stopping_distance_m, reaction_distance_m, braking_distance_m)
    """
    speed_ms = speed_kmh_to_ms(speed_kmh)

    reaction_distance_m = speed_ms * reaction_time_s
    braking_distance_m = (
        speed_ms ** 2
    ) / (2.0 * braking_deceleration_mps2)

    stopping_distance_m = (
        reaction_distance_m + braking_distance_m
    )

    return (
        stopping_distance_m,
        reaction_distance_m,
        braking_distance_m,
    )


def compute_safety_margin(
    obstacle_distance_m: float,
    stopping_distance_m: float,
    safety_buffer_m: float,
) -> float:
    """Calculate remaining distance beyond estimated stopping distance."""
    return (
        obstacle_distance_m
        - stopping_distance_m
        - safety_buffer_m
    )


def determine_status(
    safety_margin_m: float,
    safe_threshold_m: float,
    caution_threshold_m: float,
) -> tuple[str, str]:
    """
    Return the legacy margin-based classification (not the dashboard risk status).

    SAFE:    margin >= safe_threshold_m
    CAUTION: caution_threshold_m <= margin < safe_threshold_m
    DANGER:  margin < caution_threshold_m
    """
    if safety_margin_m >= safe_threshold_m:
        return (
            "SAFE",
            (
                f"Adequate estimated safety margin "
                f"({safety_margin_m:.1f} m). "
                "Maintain awareness."
            ),
        )

    if safety_margin_m >= caution_threshold_m:
        return (
            "CAUTION",
            (
                f"Limited estimated safety margin "
                f"({safety_margin_m:.1f} m). "
                "Reduce speed in the demonstration."
            ),
        )

    return (
        "DANGER",
        (
            f"Insufficient estimated safety margin "
            f"({safety_margin_m:.1f} m). "
            "The model estimates that stopping distance "
            "may exceed the available distance."
        ),
    )


def determine_obstacle_status(obstacle_distance_m: float) -> tuple[str, str]:
    """Classify current risk using the same obstacle-distance thresholds as the ESP32."""
    if obstacle_distance_m <= DEFAULT_DANGER_DISTANCE_M:
        return (
            "DANGER",
            f"Obstacle distance is {obstacle_distance_m:.2f} m "
            f"(DANGER at ≤ {DEFAULT_DANGER_DISTANCE_M:.2f} m).",
        )
    if obstacle_distance_m <= DEFAULT_CAUTION_DISTANCE_M:
        return (
            "CAUTION",
            f"Obstacle distance is {obstacle_distance_m:.2f} m "
            f"(CAUTION above {DEFAULT_DANGER_DISTANCE_M:.2f} m "
            f"through {DEFAULT_CAUTION_DISTANCE_M:.2f} m).",
        )
    return (
        "SAFE",
        f"Obstacle distance is {obstacle_distance_m:.2f} m "
        f"(SAFE above {DEFAULT_CAUTION_DISTANCE_M:.2f} m).",
    )


# ============================================================
# MAIN PREDICTION FUNCTION
# ============================================================

def predict(
    speed_kmh: float,
    obstacle_distance_m: float,
    reaction_time_s: float = DEFAULT_REACTION_TIME_S,
    braking_deceleration_mps2: float = (
        DEFAULT_BRAKING_DECELERATION_MPS2
    ),
    safety_buffer_m: float = DEFAULT_SAFETY_BUFFER_M,
    safe_threshold_m: float = DEFAULT_SAFE_THRESHOLD_M,
    caution_threshold_m: float = DEFAULT_CAUTION_THRESHOLD_M,
) -> PredictionResult:
    """Calculate distance metrics and classify current risk by obstacle distance."""

    validate_inputs(
        speed_kmh,
        obstacle_distance_m,
        reaction_time_s,
        braking_deceleration_mps2,
        safety_buffer_m,
    )

    if safe_threshold_m <= caution_threshold_m:
        raise PredictionError(
            "safe_threshold_m must be greater than caution_threshold_m"
        )

    stopping_distance_m, reaction_distance_m, braking_distance_m = (
        compute_stopping_distance(
            speed_kmh,
            reaction_time_s,
            braking_deceleration_mps2,
        )
    )

    safety_margin_m = compute_safety_margin(
        obstacle_distance_m,
        stopping_distance_m,
        safety_buffer_m,
    )

    status, explanation = determine_obstacle_status(obstacle_distance_m)

    return PredictionResult(
        stopping_distance_m=stopping_distance_m,
        safety_margin_m=safety_margin_m,
        status=status,
        explanation=explanation,
        reaction_distance_m=reaction_distance_m,
        braking_distance_m=braking_distance_m,
        speed_ms=speed_kmh_to_ms(speed_kmh),
    )


def predict_with_config(
    speed_kmh: float,
    obstacle_distance_m: float,
    config: PredictionConfig,
) -> PredictionResult:
    """Run a prediction using a PredictionConfig instance."""

    return predict(
        speed_kmh=speed_kmh,
        obstacle_distance_m=obstacle_distance_m,
        reaction_time_s=config.reaction_time_s,
        braking_deceleration_mps2=config.braking_deceleration_mps2,
        safety_buffer_m=config.safety_buffer_m,
        safe_threshold_m=config.safe_threshold_m,
        caution_threshold_m=config.caution_threshold_m,
    )


# Shared default configuration used by the dashboard.
DEFAULT_CONFIG = PredictionConfig()


# ============================================================
# BACKWARD-COMPATIBLE FUNCTIONS USED BY THE DASHBOARD
# ============================================================

def stopping_distance(speed_kmh: float) -> float:
    """Return estimated total stopping distance in metres."""
    return compute_stopping_distance(
        speed_kmh,
        DEFAULT_REACTION_TIME_S,
        DEFAULT_BRAKING_DECELERATION_MPS2,
    )[0]


def reaction_distance(speed_kmh: float) -> float:
    """Return estimated reaction distance in metres."""
    return compute_stopping_distance(
        speed_kmh,
        DEFAULT_REACTION_TIME_S,
        DEFAULT_BRAKING_DECELERATION_MPS2,
    )[1]


def braking_distance(speed_kmh: float) -> float:
    """Return estimated braking distance in metres."""
    return compute_stopping_distance(
        speed_kmh,
        DEFAULT_REACTION_TIME_S,
        DEFAULT_BRAKING_DECELERATION_MPS2,
    )[2]


def safety_margin(
    obstacle_distance_m: float,
    speed_kmh: float,
) -> float:
    """Return estimated safety margin in metres."""
    return (
        obstacle_distance_m
        - stopping_distance(speed_kmh)
        - DEFAULT_SAFETY_BUFFER_M
    )


def safety_status(margin_m: float) -> tuple[str, str]:
    """Return the legacy margin-based classification; dashboard risk uses distance."""
    return determine_status(
        margin_m,
        DEFAULT_SAFE_THRESHOLD_M,
        DEFAULT_CAUTION_THRESHOLD_M,
    )


def compute_all(
    obstacle_distance_m: float,
    speed_kmh: float,
) -> dict:
    """
    Calculate dashboard metrics and obstacle-distance risk status using DEFAULT_CONFIG.

    Preserves the dictionary keys expected by app.py.
    """
    result = predict_with_config(
        obstacle_distance_m=obstacle_distance_m,
        speed_kmh=speed_kmh,
        config=DEFAULT_CONFIG,
    )
    return {
        "obstacle_distance_m": obstacle_distance_m,
        "speed_kmh": speed_kmh,
        "reaction_distance_m": result.reaction_distance_m,
        "braking_distance_m": result.braking_distance_m,
        "stopping_distance_m": result.stopping_distance_m,
        "safety_margin_m": result.safety_margin_m,
        "status": result.status,
        "explanation": result.explanation,
    }


# ============================================================
# DEMO SCENARIOS
# ============================================================

DEMO_SCENARIOS = [
    {
        "name": "Highway - Safe",
        "obstacle_distance_m": 120.0,
        "speed_kmh": 80.0,
    },
    {
        "name": "Highway - Caution",
        "obstacle_distance_m": 70.0,
        "speed_kmh": 100.0,
    },
    {
        "name": "Highway - Danger",
        "obstacle_distance_m": 50.0,
        "speed_kmh": 120.0,
    },
    {
        "name": "Urban - Safe",
        "obstacle_distance_m": 40.0,
        "speed_kmh": 40.0,
    },
    {
        "name": "Urban - Caution",
        "obstacle_distance_m": 25.0,
        "speed_kmh": 50.0,
    },
    {
        "name": "Urban - Danger",
        "obstacle_distance_m": 15.0,
        "speed_kmh": 60.0,
    },
]
