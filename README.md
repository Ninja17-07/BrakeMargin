# BrakeMargin — Predictive Braking Safety Dashboard

A minimalistic Streamlit dashboard for visualising braking safety margins. Designed for a 24-hour hardware hackathon with **DEMO MODE** that works immediately without any hardware.

## Features

- **Demo Mode**: Realistic simulated scenarios (Safe, Caution, Danger) — no hardware needed
- **Live Metrics**: Obstacle distance, speed, stopping distance, safety margin
- **Distance Comparison**: Current obstacle distance vs. estimated stopping distance
- **Status Indicators**: SAFE / CAUTION / DANGER with explanations
- **Demo Controls**: Select SAFE, CAUTION, or DANGER presets and adjust simulated speed and obstacle distance
- **Hardware Mode**: Optional USB serial input with newline-delimited JSON, port-open status, and stale/error handling

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Dashboard

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`

## Project Structure

```
BrakeMargin/
├── app.py              # Main Streamlit dashboard
├── prediction.py       # Physics calculations (stopping distance, safety margin)
├── data_source.py      # Demo & hardware data sources
├── serial_reader.py    # Background newline-delimited JSON USB serial reader
├── sensor_types.py     # Shared sensor reading type
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Dashboard Overview

### Metrics Displayed

| Metric | Description |
|--------|-------------|
| **Obstacle Distance** | Distance to detected obstacle (metres) |
| **Simulated Speed** | Current vehicle speed (km/h) |
| **Stopping Distance** | Estimated total stopping distance (metres) |
| **Safety Margin** | Obstacle distance − Stopping distance − safety buffer (metres) |

### Current Risk Status (obstacle distance; matches ESP32 LEDs)

| Status | Obstacle distance | Meaning |
|--------|--------|---------|
| 🔴 **DANGER** | ≤ 0.20 m | Obstacle is within the danger threshold |
| 🟡 **CAUTION** | >0.20–≤0.70 m | Obstacle is within the caution range |
| 🟢 **SAFE** | >0.70 m | Obstacle is beyond the caution threshold |
| **SENSOR DATA UNAVAILABLE** | No valid, fresh reading | No current risk classification is made |

### Charts

1. **Obstacle & Stopping Distance** — Live time series of valid readings.
2. **Safety Margin** — Live time series of the calculated margin; it does not determine the current risk status.
3. **Vehicle Visualization** — Self-contained illustration showing current obstacle and estimated stopping distances.
4. **Live Status** — Current metrics and risk state, synchronized with the metric cards and demo controls.

## Demo Mode Usage

1. Start the dashboard in **Demo Mode** (default; no hardware connection is made).
2. Choose a **SAFE**, **CAUTION**, or **DANGER** preset. Preset obstacle distances are 5.0 m, 0.5 m, and 0.1 m respectively, matching the ESP32 distance thresholds.
3. Adjust simulated speed and obstacle distance with the controls. Metrics, status, illustration, and charts update together.

## Safety Assumptions (Documented in `prediction.py`)

> **⚠️ IMPORTANT: These are ESTIMATES only — not guaranteed stopping distances.**

| Parameter | Value | Basis |
|-----------|-------|-------|
| Driver reaction time | 1.5 s | Demonstration assumption only |
| Braking deceleration | 5.0 m/s² | Demonstration assumption only |
| Road gradient | 0% | Flat road assumed |
| Safety buffer | 0.0 m | Demonstration assumption only |

These values are illustrative and are **not verified vehicle braking
characteristics**. BrakeMargin is a student prototype, not a certified vehicle
safety or automatic braking system, and does not guarantee collision avoidance.

**Formulas:**
- Reaction distance = v × t_reaction
- Braking distance = v² / (2 × a)
- Stopping distance = Reaction distance + Braking distance
- Safety margin = Obstacle distance − Stopping distance − safety buffer

Where v = speed in m/s, a = deceleration in m/s².

## Hardware Mode

Hardware Mode is ready to read newline-delimited JSON from a USB serial device.
Select an enumerated serial port and press **Connect**. The reader uses 115200
baud and runs outside the Streamlit rendering thread. The connection indicator means the serial port opened successfully; it does not
verify the identity of the device. The companion [BrakeMargin.ino](./BrakeMargin.ino)
firmware implements the same distance-based risk thresholds as the dashboard.
Stopping-distance and safety-margin calculations remain separate estimates and
do not determine the current risk label.

Each line must be a UTF-8 JSON object with finite, non-negative numeric fields:

```json
{"obstacle_distance_m": 18.5, "speed_kmh": 42.0}
```

The line must end with `\n`. A sensor can report an error as
`{"error": "distance sensor timeout"}`. Invalid JSON, missing or invalid
fields, decoding errors, sensor errors, and serial read failures are surfaced
in the dashboard and make the current reading unavailable. Data older than
2.5 seconds is marked stale and removed from the current metrics. Time-series
charts retain at most 300 valid readings. Hardware Mode never falls back to
simulated values.

The ESP32 sketch reports every 500 ms at 115200 baud. Close Arduino Serial
Monitor before connecting from Streamlit because the serial port can only be
opened by one program at a time.

## Development

### Running Syntax Checks

```bash
# Check Python syntax
python -m py_compile app.py prediction.py data_source.py

# Or use a linter
pip install ruff
ruff check .
```

### Testing Calculations

```python
from prediction import compute_all

# Test a scenario
result = compute_all(obstacle_distance_m=50.0, speed_kmh=80.0)
print(result)
# {'obstacle_distance_m': 50.0, 'speed_kmh': 80.0, 'reaction_distance_m': 33.3,
#  'braking_distance_m': 25.2, 'stopping_distance_m': 58.5, 'safety_margin_m': -8.5,
#  'status': 'DANGER', 'explanation': 'Stopping distance exceeds obstacle distance...'}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Port already in use | Streamlit defaults to 8501; use `streamlit run app.py --server.port 8502` |
| Charts not updating | Enable Auto-play or switch scenarios manually |
| Hardware mode fails | Hardware integration not yet implemented; use Demo Mode |

## License

MIT License — Built for a road-safety hardware hackathon.