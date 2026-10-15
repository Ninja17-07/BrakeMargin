import json
import queue
import time

import pytest

import serial_reader
from data_source import DemoDataSource, HardwareDataSource
from serial_reader import NDJSONSerialReader, parse_sensor_line


def test_hardware_source_starts_disconnected_without_fake_values():
    source = HardwareDataSource(port="COM-not-attached")
    reading = source.read()
    assert not source.is_connected
    assert not reading.valid
    assert reading.source == "hardware"
    assert reading.obstacle_distance_m is None
    assert reading.speed_kmh is None


def test_demo_control_values_are_returned_without_noise():
    source = DemoDataSource()
    source.set_values(obstacle_distance_m=0.0, speed_kmh=57.0)
    reading = source.read()
    assert reading.valid
    assert reading.source == "demo"
    assert reading.obstacle_distance_m == 0.0
    assert reading.speed_kmh == 57.0


def test_parse_sensor_line():
    assert parse_sensor_line(
        '{"obstacle_distance_m": 18.25, "speed_kmh": 42}'
    ) == (18.25, 42.0)


@pytest.mark.parametrize(
    "line",
    [
        "not json",
        "[]",
        '{"obstacle_distance_m": -1, "speed_kmh": 20}',
        '{"obstacle_distance_m": 10, "speed_kmh": true}',
        '{"obstacle_distance_m": NaN, "speed_kmh": 20}',
        '{"obstacle_distance_m": 10}',
        '{"error": "sensor timeout"}',
    ],
)
def test_parse_sensor_line_rejects_invalid_messages(line):
    with pytest.raises((TypeError, ValueError)):
        parse_sensor_line(line)


class FakeSerial:
    def __init__(self, **_kwargs):
        self.is_open = True
        self.lines = queue.Queue()

    def readline(self):
        try:
            return self.lines.get(timeout=0.02)
        except queue.Empty:
            return b""

    def close(self):
        self.is_open = False


def test_reader_reports_only_fresh_hardware_values(monkeypatch):
    fake_serial = FakeSerial()
    monkeypatch.setattr(serial_reader.serial, "Serial", lambda **_kwargs: fake_serial)
    reader = NDJSONSerialReader("COM-test", stale_after_s=0.05)
    assert reader.connect()
    try:
        message = json.dumps({"obstacle_distance_m": 21.5, "speed_kmh": 35}).encode() + b"\n"
        split_at = len(message) // 2
        fake_serial.lines.put(message[:split_at])
        time.sleep(0.03)
        assert not reader.read().valid
        fake_serial.lines.put(message[split_at:])
        deadline = time.monotonic() + 1.0
        reading = reader.read()
        while not reading.valid and time.monotonic() < deadline:
            time.sleep(0.01)
            reading = reader.read()
        assert reading.valid
        assert reading.source == "hardware"
        assert reading.obstacle_distance_m == 21.5
        assert reading.speed_kmh == 35

        fake_serial.lines.put(b"not json\n")
        deadline = time.monotonic() + 1.0
        reading = reader.read()
        while reading.error is None and time.monotonic() < deadline:
            time.sleep(0.01)
            reading = reader.read()
        assert not reading.valid
        assert "invalid sensor message" in reading.error.lower()
        assert reading.obstacle_distance_m is None

        fake_serial.lines.put(message)
        deadline = time.monotonic() + 1.0
        reading = reader.read()
        while not reading.valid and time.monotonic() < deadline:
            time.sleep(0.01)
            reading = reader.read()
        assert reading.valid

        time.sleep(0.07)
        stale = reader.read()
        assert stale.stale
        assert not stale.valid
        assert stale.obstacle_distance_m is None
        assert stale.speed_kmh is None
        assert "stale" in stale.error.lower()
        reader.disconnect()
        disconnected = reader.read()
        assert not disconnected.valid
        assert disconnected.obstacle_distance_m is None
        assert "disconnected" in disconnected.error.lower()
    finally:
        reader.disconnect()
