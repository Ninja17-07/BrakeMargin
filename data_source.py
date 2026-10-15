"""
BrakeMargin - Data Source Module

Provides data sources for the dashboard:
- DemoDataSource: Generates simulated data for testing without hardware
- HardwareDataSource: Reads validated newline-delimited JSON over USB serial

Design principle: The dashboard should never crash due to invalid readings.
All data sources return valid Python types or safe defaults.
"""

import random
import time

from prediction import DEMO_SCENARIOS
from sensor_types import SensorReading
from serial_reader import NDJSONSerialReader


class DemoDataSource:
    """
    Demo data source that simulates realistic driving scenarios.
    
    Features:
    - Pre-defined scenarios (safe, caution, danger)
    - Optional auto-play mode that cycles through scenarios
    - Smooth transitions between values
    - Never returns None for required values
    """
    
    def __init__(self, auto_play: bool = False, scenario_index: int = 0):
        self.auto_play = auto_play
        self.scenario_index = scenario_index
        self._start_time = time.time()
        self._last_update = self._start_time
        self._current_obstacle = DEMO_SCENARIOS[scenario_index]["obstacle_distance_m"]
        self._current_speed = DEMO_SCENARIOS[scenario_index]["speed_kmh"]
        self._target_obstacle = self._current_obstacle
        self._target_speed = self._current_speed
        self._manual_values = False
        self._transition_start = self._start_time
        self._transition_duration = 3.0  # seconds
        
    def set_scenario(self, index: int) -> None:
        """Switch to a specific demo scenario with smooth transition."""
        if 0 <= index < len(DEMO_SCENARIOS):
            self.scenario_index = index
            self._manual_values = False
            scenario = DEMO_SCENARIOS[index]
            self._target_obstacle = scenario["obstacle_distance_m"]
            self._target_speed = scenario["speed_kmh"]
            self._transition_start = time.time()
            
    def set_auto_play(self, enabled: bool) -> None:
        """Enable or disable automatic scenario cycling."""
        self.auto_play = enabled
        if enabled:
            self._transition_start = time.time()
            
    def _interpolate(self, current: float, target: float, progress: float) -> float:
        """Smooth interpolation with easing."""
        # Ease-in-out cubic
        eased = 3 * progress * progress - 2 * progress * progress * progress
        return current + (target - current) * eased
    
    def read(self) -> SensorReading:
        """
        Get current simulated sensor reading.
        
        Returns SensorReading with valid=True and realistic values.
        """
        now = time.time()
        
        # Handle auto-play scenario cycling
        if self.auto_play:
            cycle_time = (now - self._start_time) % 18.0  # 3 scenarios × ~6s each
            scenario_idx = int(cycle_time / 6.0) % len(DEMO_SCENARIOS)
            if scenario_idx != self.scenario_index:
                self.set_scenario(scenario_idx)
        
        # Smooth transition to target values
        elapsed = now - self._transition_start
        progress = (
            1.0
            if self._transition_duration <= 0
            else min(elapsed / self._transition_duration, 1.0)
        )
        
        self._current_obstacle = self._interpolate(
            self._current_obstacle, self._target_obstacle, progress
        )
        self._current_speed = self._interpolate(
            self._current_speed, self._target_speed, progress
        )
        
        # Add small realistic noise (±2%)
        noise_factor = 0.02
        obstacle_noise = (
            0.0
            if self._manual_values
            else self._current_obstacle * random.uniform(-noise_factor, noise_factor)
        )
        speed_noise = (
            0.0
            if self._manual_values
            else self._current_speed * random.uniform(-noise_factor, noise_factor)
        )
        
        # Ensure physically plausible values
        minimum_distance = 0.0 if self._manual_values else 0.5
        obstacle_distance = max(minimum_distance, self._current_obstacle + obstacle_noise)
        speed = max(0.0, self._current_speed + speed_noise)
        
        return SensorReading(
            obstacle_distance_m=round(obstacle_distance, 1),
            speed_kmh=round(speed, 1),
            timestamp=now,
            source="demo",
            valid=True
        )
    
    def get_scenario_name(self) -> str:
        """Get current scenario display name."""
        return DEMO_SCENARIOS[self.scenario_index]["name"]
    
    def get_available_scenarios(self) -> list[str]:
        """Get list of all scenario names for UI selection."""
        return [s["name"] for s in DEMO_SCENARIOS]

    def set_values(self, obstacle_distance_m: float, speed_kmh: float) -> None:
        """Set exact values from the interactive demo controls."""
        self._target_obstacle = obstacle_distance_m
        self._target_speed = speed_kmh
        self._current_obstacle = obstacle_distance_m
        self._current_speed = speed_kmh
        self._manual_values = True
        self._transition_start = time.time()
        self._transition_duration = 0.0


class HardwareDataSource:
    """
    Read newline-delimited JSON sensor readings from a USB serial device.

    Each JSON object must contain numeric ``obstacle_distance_m`` and
    ``speed_kmh`` fields. The serial reader owns parsing and thread management.
    """

    def __init__(self, port: str = "COM3", baudrate: int = 115200, stale_after_s: float = 2.5):
        self.port = port
        self.baudrate = baudrate
        self.reader = NDJSONSerialReader(
            port=port,
            baudrate=baudrate,
            stale_after_s=stale_after_s,
        )
        
    def connect(self) -> bool:
        """Open the selected USB serial port and begin reading."""
        return self.reader.connect()
    
    def disconnect(self) -> None:
        """Stop the reader and close the serial port."""
        self.reader.disconnect()
        
    def read(self) -> SensorReading:
        """Return only a fresh valid reading; errors never become fake values."""
        return self.reader.read()
    
    @property
    def is_connected(self) -> bool:
        return self.reader.is_connected

    @property
    def last_error(self) -> str | None:
        return self.reader.last_error


def create_data_source(mode: str, **kwargs) -> DemoDataSource | HardwareDataSource:
    """
    Factory function to create appropriate data source.
    
    Args:
        mode: "demo" or "hardware"
        **kwargs: Additional arguments passed to constructor
        
    Returns:
        Data source instance
    """
    if mode == "hardware":
        return HardwareDataSource(**kwargs)
    return DemoDataSource(**kwargs)


def list_serial_ports() -> list[str]:
    """Return currently enumerated serial-port device names."""
    from serial.tools import list_ports

    return [port.device for port in list_ports.comports()]