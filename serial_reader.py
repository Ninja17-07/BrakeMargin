"""Threaded newline-delimited JSON reader for USB serial sensor devices."""

import json
import math
import threading
import time

import serial

from sensor_types import SensorReading


def _finite_nonnegative_number(payload: dict, field: str) -> float:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"'{field}' must be a number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"'{field}' must be finite and non-negative")
    return float(value)


def parse_sensor_line(line: str) -> tuple[float, float]:
    """Parse a JSON object containing obstacle_distance_m and speed_kmh."""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise TypeError("Sensor message must be a JSON object")
    if payload.get("error"):
        raise ValueError(f"Sensor reported an error: {payload['error']}")
    distance = _finite_nonnegative_number(payload, "obstacle_distance_m")
    speed = _finite_nonnegative_number(payload, "speed_kmh")
    return distance, speed


class NDJSONSerialReader:
    """Read and validate sensor messages without blocking Streamlit rendering."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        stale_after_s: float = 2.5,
    ) -> None:
        if stale_after_s <= 0:
            raise ValueError("stale_after_s must be positive")
        self.port = port
        self.baudrate = baudrate
        self.stale_after_s = stale_after_s
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest: SensorReading | None = None
        self._latest_received_monotonic: float | None = None
        self._last_error: str | None = None
        self._connected = False

    def connect(self) -> bool:
        """Open the USB port and launch a background serial reader."""
        if self.is_connected:
            return True
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.2,
            )
        except (serial.SerialException, OSError) as error:
            with self._lock:
                self._last_error = f"Could not open {self.port}: {error}"
                self._connected = False
            return False

        self._stop_event.clear()
        with self._lock:
            self._latest = None
            self._latest_received_monotonic = None
            self._last_error = None
            self._connected = True
        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"BrakeMargin serial reader ({self.port})",
            daemon=True,
        )
        self._thread.start()
        return True

    def disconnect(self) -> None:
        """Stop the reader and close the port, safely handling repeated calls."""
        self._stop_event.set()
        serial_port = self._serial
        self._serial = None
        if serial_port is not None and serial_port.is_open:
            serial_port.close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        with self._lock:
            self._connected = False

    def read(self) -> SensorReading:
        """Return the latest fresh reading, or an explicit waiting/stale error."""
        now = time.time()
        with self._lock:
            latest = self._latest
            received_at = self._latest_received_monotonic
            error = self._last_error
            connected = (
                self._connected
                and self._serial is not None
                and self._serial.is_open
            )

        if latest is None:
            message = error or (
                "Waiting for the first sensor reading."
                if connected
                else "Serial port is disconnected."
            )
            return SensorReading(None, None, now, "hardware", False, error=message)

        if not connected:
            return SensorReading(
                None,
                None,
                latest.timestamp,
                "hardware",
                False,
                error=error or "Serial port is disconnected.",
            )

        age_s = (
            time.monotonic() - received_at
            if received_at is not None
            else self.stale_after_s + 1
        )
        if age_s > self.stale_after_s:
            message = f"Sensor data is stale ({age_s:.1f} s since last valid message)."
            if error:
                message = f"{message} Latest reader error: {error}"
            return SensorReading(None, None, latest.timestamp, "hardware", False, stale=True, error=message)

        return SensorReading(
            latest.obstacle_distance_m,
            latest.speed_kmh,
            latest.timestamp,
            "hardware",
            True,
            error=error,
        )

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected and self._serial is not None and self._serial.is_open

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def _read_loop(self) -> None:
        serial_port = self._serial
        if serial_port is None:
            return
        line_buffer = bytearray()
        while not self._stop_event.is_set():
            try:
                chunk = serial_port.readline()
            except (serial.SerialException, OSError) as error:
                if not self._stop_event.is_set():
                    with self._lock:
                        self._last_error = f"Serial read failed on {self.port}: {error}"
                        self._connected = False
                break
            if not chunk:
                continue
            line_buffer.extend(chunk)
            if len(line_buffer) > 4096:
                with self._lock:
                    self._last_error = "Invalid sensor message: line exceeds 4096 bytes."
                line_buffer.clear()
                continue

            while b"\n" in line_buffer:
                line, _, remainder = line_buffer.partition(b"\n")
                line_buffer = bytearray(remainder)
                try:
                    decoded = line.decode("utf-8").strip()
                    if not decoded:
                        continue
                    distance, speed = parse_sensor_line(decoded)
                except (UnicodeDecodeError, TypeError, ValueError) as error:
                    with self._lock:
                        self._latest = None
                        self._latest_received_monotonic = None
                        self._last_error = f"Invalid sensor message: {error}"
                    continue

                received_at = time.monotonic()
                reading = SensorReading(
                    distance,
                    speed,
                    time.time(),
                    "hardware",
                    True,
                )
                with self._lock:
                    self._latest = reading
                    self._latest_received_monotonic = received_at
                    self._last_error = None

        if not self._stop_event.is_set():
            serial_port.close()
