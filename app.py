"""BrakeMargin - Predictive Braking Safety Dashboard.

Run locally with: streamlit run app.py
"""

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from data_source import DemoDataSource, HardwareDataSource, list_serial_ports
from prediction import (
    DEFAULT_CAUTION_DISTANCE_M,
    DEFAULT_CONFIG,
    DEFAULT_DANGER_DISTANCE_M,
    PredictionError,
    compute_all,
)
from sensor_types import SensorReading, sensor_data_status

st.set_page_config(
    page_title="BrakeMargin | Predictive Braking Safety",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded",
)


COLORS = {
    "background": "#080d17",
    "card": "#101827",
    "border": "#202c3d",
    "text": "#eef3fa",
    "muted": "#91a0b5",
    "blue": "#4b9bff",
    "green": "#37d39a",
    "amber": "#f5b84b",
    "red": "#ff6673",
}

STATUS_COLORS = {
    "SAFE": COLORS["green"],
    "CAUTION": COLORS["amber"],
    "DANGER": COLORS["red"],
    "SENSOR DATA UNAVAILABLE": COLORS["muted"],
}

CAR_ICON = """
<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="m5 18 2-7a3 3 0 0 1 3-2h12a3 3 0 0 1 3 2l2 7"/>
  <path d="M4 18h24v6H4zM8 24v2m16-2v2M8 18l2-5h12l2 5"/>
  <circle cx="9" cy="21" r="1"/><circle cx="23" cy="21" r="1"/>
</svg>
"""

METRIC_ICONS = {
    "distance": """
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M4 12h16M4 12l4-4m-4 4 4 4m12-4-4-4m4 4-4 4"/>
      <path d="M8 5v2m4-2v2m4-2v2M8 17v2m4-2v2m4-2v2"/>
    </svg>
    """,
    "speed": """
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M4.9 19a9 9 0 1 1 14.2 0"/><path d="m12 13 4-4"/>
      <path d="M7 19h10"/>
    </svg>
    """,
    "brake": """
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>
      <path d="M3 12h2m14 0h2M12 3v2m0 14v2"/>
    </svg>
    """,
    "margin": """
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M4 7h16M4 17h16M7 4 4 7l3 3m10 4 3 3-3 3"/>
    </svg>
    """,
}


def preset_values(status: str) -> tuple[float, float]:
    """Return a demo speed and distance that trigger the requested hardware status."""
    speed = 60.0
    distance = {"SAFE": 5.0, "CAUTION": 0.5, "DANGER": 0.1}[status]
    return speed, distance


def apply_preset() -> None:
    speed, distance = preset_values(st.session_state.scenario)
    st.session_state.simulated_speed = speed
    st.session_state.obstacle_distance = distance


def render_metric(
    label: str,
    value: str,
    unit: str,
    subtitle: str,
    icon: str,
    accent: str,
) -> None:
    st.markdown(
        f"""
        <div class="metric-card" style="--metric-accent:{accent}">
          <div class="metric-heading">
            <span class="metric-icon">{icon}</span>
            <span class="metric-label">{label}</span>
          </div>
          <div class="metric-value">{value}<span class="metric-unit">{unit}</span></div>
          <div class="metric-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def create_distance_chart(
    obstacle_distance: float | None,
    stopping_distance: float | None,
) -> go.Figure:
    """Show a direct comparison of this reading, not a fabricated time series."""
    figure = go.Figure()
    if obstacle_distance is None or stopping_distance is None:
        figure.add_annotation(
            text="Waiting for a fresh, valid sensor reading",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": COLORS["muted"], "size": 13},
        )
        figure.update_layout(
            height=245,
            margin={"l": 10, "r": 18, "t": 16, "b": 38},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return figure
    figure.add_trace(
        go.Bar(
            x=[obstacle_distance],
            y=["Current reading"],
            name="Obstacle distance",
            orientation="h",
            marker_color=COLORS["blue"],
            hovertemplate="Obstacle distance: %{x:.1f} m<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=[stopping_distance],
            y=["Current reading"],
            name="Estimated stopping distance",
            orientation="h",
            marker_color=COLORS["red"],
            hovertemplate="Estimated stopping distance: %{x:.1f} m<extra></extra>",
        )
    )
    figure.update_layout(
        barmode="group",
        bargap=0.45,
        height=245,
        margin={"l": 10, "r": 18, "t": 16, "b": 38},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Segoe UI, sans-serif", "color": COLORS["muted"], "size": 11},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"color": COLORS["muted"], "size": 10},
        },
        xaxis={
            "title": "Distance (m)",
            "rangemode": "tozero",
            "gridcolor": "rgba(145,160,181,0.13)",
            "zeroline": False,
            "tickfont": {"color": COLORS["muted"]},
            "title_font": {"color": COLORS["muted"]},
        },
        yaxis={
            "showgrid": False,
            "tickfont": {"color": COLORS["muted"]},
            "title": None,
        },
        hoverlabel={"bgcolor": COLORS["card"], "font_color": COLORS["text"]},
    )
    return figure


def create_history_charts(
    history: list[dict[str, float]],
) -> tuple[go.Figure, go.Figure]:
    """Build bounded live distance and safety-margin time-series charts."""
    timestamps = [
        datetime.fromtimestamp(point["timestamp"]).astimezone()
        for point in history
    ]
    distance_figure = go.Figure()
    margin_figure = go.Figure()
    if history:
        distance_figure.add_trace(
            go.Scatter(
                x=timestamps,
                y=[point["obstacle_distance_m"] for point in history],
                name="Obstacle distance",
                mode="lines",
                line={"color": COLORS["blue"], "width": 2},
            )
        )
        distance_figure.add_trace(
            go.Scatter(
                x=timestamps,
                y=[point["stopping_distance_m"] for point in history],
                name="Estimated stopping distance",
                mode="lines",
                line={"color": COLORS["red"], "width": 2},
            )
        )
        margin_figure.add_trace(
            go.Scatter(
                x=timestamps,
                y=[point["safety_margin_m"] for point in history],
                name="Safety margin",
                mode="lines",
                line={"color": COLORS["green"], "width": 2},
                fill="tozeroy",
                fillcolor="rgba(55,211,154,0.10)",
            )
        )
        margin_figure.add_hline(
            y=0,
            line_color=COLORS["muted"],
            line_dash="dash",
            annotation_text="Zero margin",
            annotation_position="top left",
        )
    else:
        for figure in (distance_figure, margin_figure):
            figure.add_annotation(
                text="Waiting for valid sensor readings",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font={"color": COLORS["muted"], "size": 13},
            )
    for figure, y_title in (
        (distance_figure, "Distance (m)"),
        (margin_figure, "Safety margin (m)"),
    ):
        figure.update_layout(
            height=300,
            margin={"l": 10, "r": 18, "t": 20, "b": 38},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "Inter, Segoe UI, sans-serif", "color": COLORS["muted"], "size": 11},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "font": {"color": COLORS["muted"], "size": 10},
            },
            xaxis={
                "title": "Time",
                "gridcolor": "rgba(145,160,181,0.13)",
                "tickformat": "%H:%M:%S",
            },
            yaxis={
                "title": y_title,
                "gridcolor": "rgba(145,160,181,0.13)",
            },
            hoverlabel={"bgcolor": COLORS["card"], "font_color": COLORS["text"]},
        )
    return distance_figure, margin_figure


def create_road_illustration(
    obstacle_distance: float,
    stopping_distance: float,
    status: str,
) -> str:
    """Draw a responsive, self-contained SVG using the current prediction values."""
    car_front = 145.0
    obstacle_x = 745.0
    available_span = obstacle_x - car_front
    stopping_ratio = stopping_distance / obstacle_distance if obstacle_distance > 0 else 1.0
    stop_x = car_front + available_span * min(max(stopping_ratio, 0.0), 1.0)
    accent = STATUS_COLORS[status]
    margin_label = (
        f"{abs(obstacle_distance - stopping_distance):.1f} m remaining"
        if obstacle_distance >= stopping_distance
        else f"{stopping_distance - obstacle_distance:.1f} m beyond obstacle"
    )
    return f"""
    <svg viewBox="0 0 800 210" role="img"
         aria-label="Car, estimated stopping point, and obstacle at {obstacle_distance:.1f} metres">
      <defs>
        <linearGradient id="roadGlow" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#4b9bff" stop-opacity=".10"/>
          <stop offset="1" stop-color="#4b9bff" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <rect x="28" y="40" width="744" height="116" rx="18" fill="url(#roadGlow)"/>
      <path d="M36 151H764" stroke="#2a374b" stroke-width="3" stroke-linecap="round"/>
      <path d="M46 168H754" stroke="#202c3d" stroke-width="19" stroke-linecap="round"/>
      <path d="M70 168h48m34 0h48m34 0h48m34 0h48m34 0h48m34 0h48m34 0h48m34 0h48"
            stroke="#526176" stroke-width="2" stroke-dasharray="18 18" opacity=".45"/>
      <path d="M{car_front:.1f} 115H{obstacle_x:.1f}" stroke="#344258" stroke-width="1"
            stroke-dasharray="4 8"/>
      <path d="M{car_front:.1f} 83H{obstacle_x:.1f}" stroke="#4b9bff" stroke-width="2"
            opacity=".72"/>
      <path d="M{car_front:.1f} 77v12M{obstacle_x:.1f} 77v12" stroke="#4b9bff"
            stroke-width="2"/>
      <rect x="374" y="57" width="142" height="28" rx="14" fill="#14243a"
            stroke="#29466a"/>
      <text x="445" y="76" text-anchor="middle" fill="#8ec1ff" font-size="13"
            font-family="Segoe UI, sans-serif" font-weight="700">
        {obstacle_distance:.1f} m to obstacle
      </text>
      <path d="M{car_front:.1f} 130H{stop_x:.1f}" stroke="{accent}" stroke-width="3"
            stroke-dasharray="7 6" opacity=".9"/>
      <path d="M{stop_x:.1f} 121v18" stroke="{accent}" stroke-width="3"/>
      <text x="{(car_front + stop_x) / 2:.1f}" y="122" text-anchor="middle"
            fill="{accent}" font-size="11" font-family="Segoe UI, sans-serif" font-weight="600">
        estimated stop · {stopping_distance:.1f} m
      </text>
      <g transform="translate(62 101)">
        <path d="M7 25 16 6q3-6 10-6h43q7 0 11 6l12 19v22H7z"
              fill="#17283e" stroke="#4b9bff" stroke-width="2"/>
        <path d="m24 9 5-3h36l9 14H18z" fill="#27496d"/>
        <path d="M9 29h81" stroke="#4b9bff" stroke-width="2"/>
        <circle cx="26" cy="47" r="8" fill="#080d17" stroke="#8394aa" stroke-width="3"/>
        <circle cx="72" cy="47" r="8" fill="#080d17" stroke="#8394aa" stroke-width="3"/>
      </g>
      <text x="105" y="204" text-anchor="middle" fill="#91a0b5" font-size="10"
            font-family="Segoe UI, sans-serif" letter-spacing="1.2">SIMULATED VEHICLE</text>
      <g transform="translate(727 100)">
        <path d="M18 0v51" stroke="#ff6673" stroke-width="5" stroke-linecap="round"/>
        <path d="M4 10h29M4 23h29M4 36h29" stroke="#ff6673" stroke-width="5"
              stroke-linecap="round" opacity=".82"/>
        <path d="M5 51h27" stroke="#8290a4" stroke-width="3" stroke-linecap="round"/>
      </g>
      <text x="745" y="204" text-anchor="middle" fill="#91a0b5" font-size="10"
            font-family="Segoe UI, sans-serif" letter-spacing="1.2">OBSTACLE</text>
      <text x="746" y="100" text-anchor="end" fill="{accent}" font-size="11"
            font-family="Segoe UI, sans-serif" font-weight="600">{margin_label}</text>
    </svg>
    """


st.markdown(
    """
    <style>
    :root {
      color-scheme: dark;
      --bm-bg: #080d17;
      --bm-card: #101827;
      --bm-border: #202c3d;
      --bm-text: #eef3fa;
      --bm-muted: #91a0b5;
      --bm-blue: #4b9bff;
    }
    .stApp { background: var(--bm-bg); color: var(--bm-text); }
    [data-testid="stAppViewContainer"] { background: var(--bm-bg); }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1500px; padding-top: 1.2rem; padding-bottom: 1.6rem; }
    #MainMenu, footer, .stDeployButton { visibility: hidden; }
    [data-testid="stMainMenuButton"] { visibility: hidden; }
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapseButton"] { visibility: visible !important; }
    section[data-testid="stSidebar"] {
      background: #0b1220;
      border-right: 1px solid var(--bm-border);
    }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: var(--bm-text); }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--bm-muted); }
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-testid="stSlider"] {
      background-color: #111b2a;
    }
    .dashboard-header {
      display:flex; align-items:center; justify-content:space-between; gap:1rem;
      padding:.25rem 0 1.05rem; margin-bottom:1.15rem;
      border-bottom:1px solid var(--bm-border);
    }
    .brand { display:flex; align-items:center; gap:.85rem; min-width:0; }
    .brand-mark {
      width:48px; height:48px; display:grid; place-items:center; flex:0 0 auto;
      color:var(--bm-blue); border:1px solid #29466a; border-radius:14px;
      background:linear-gradient(145deg,#172c46,#0e1929);
    }
    .brand-mark svg { width:30px; height:30px; }
    .wordmark { font-size:1.8rem; line-height:1.08; font-weight:800; letter-spacing:-.06em; }
    .wordmark span { color:var(--bm-blue); }
    .tagline { color:var(--bm-muted); font-size:.78rem; margin-top:.3rem; }
    .device-pill {
      display:flex; align-items:center; gap:.55rem; color:#9dc8ff;
      border:1px solid #263c59; border-radius:999px; padding:.55rem .85rem;
      background:#101c2d; font-size:.72rem; font-weight:700; white-space:nowrap;
      letter-spacing:.06em;
    }
    .device-pill.connected { color:#8ce3bd; border-color:#24523f; background:#10231e; }
    .device-pill.disconnected { color:#a7b2c2; border-color:#344052; background:#111925; }
    .device-pill.stale, .device-pill.waiting { color:#f5ca79; border-color:#5b4928; background:#261f13; }
    .device-dot { width:7px; height:7px; border-radius:50%; background:var(--bm-blue);
      box-shadow:0 0 10px #4b9bff88; }
    .device-dot.connected { background:#37d39a; box-shadow:0 0 10px #37d39a88; }
    .device-dot.disconnected { background:#778398; box-shadow:none; }
    .device-dot.stale, .device-dot.waiting { background:#f5b84b; box-shadow:0 0 10px #f5b84b88; }
    .metric-card {
      height:100%; min-height:139px; box-sizing:border-box; padding:1rem 1.05rem;
      border:1px solid var(--bm-border); border-radius:15px; background:
        linear-gradient(145deg,#121d2d,#0e1623); transition:border-color .18s ease;
    }
    .metric-card:hover { border-color:#34465f; }
    .metric-heading { display:flex; align-items:center; gap:.65rem; }
    .metric-icon { display:grid; place-items:center; width:34px; height:34px;
      border-radius:10px; color:var(--metric-accent); background:color-mix(in srgb,var(--metric-accent) 12%,transparent); }
    .metric-icon svg { width:20px; height:20px; }
    .metric-label { color:#a8b5c7; font-size:.72rem; font-weight:650; letter-spacing:.045em; }
    .metric-value { margin-top:.8rem; color:var(--metric-accent); font-size:1.85rem;
      line-height:1; font-weight:760; letter-spacing:-.04em; white-space:nowrap; }
    .metric-unit { color:#8796aa; font-size:.85rem; font-weight:500; letter-spacing:0; margin-left:.28rem; }
    .metric-subtitle { margin-top:.52rem; color:#718198; font-size:.69rem; line-height:1.4; }
    [data-testid="stVerticalBlockBorderWrapper"] {
      background:linear-gradient(145deg,#111a29,#0e1623);
      border:1px solid var(--bm-border); border-radius:16px; padding:1rem 1.15rem;
    }
    .section-kicker { color:#8392a8; font-size:.68rem; font-weight:700;
      letter-spacing:.11em; text-transform:uppercase; }
    .safety-panel { margin-top:1rem; }
    .safety-title { color:#dce6f3; font-weight:650; font-size:.92rem; margin:.28rem 0 .15rem; }
    .safety-subtitle { color:#718198; font-size:.72rem; }
    .road-illustration { width:100%; margin-top:.45rem; }
    .road-illustration svg { display:block; width:100%; height:auto; max-height:200px; }
    .status-card {
      height:100%; min-height:180px; box-sizing:border-box; display:flex;
      flex-direction:column; align-items:flex-start; justify-content:center;
      border:1px solid color-mix(in srgb,var(--status-accent) 35%,#202c3d);
      border-radius:14px; padding:1.1rem 1.2rem;
      background:linear-gradient(145deg,color-mix(in srgb,var(--status-accent) 9%,#101827),#101827);
    }
    .status-icon { width:38px; height:38px; color:var(--status-accent); }
    .status-icon svg { width:100%; height:100%; }
    .status-name { color:var(--status-accent); font-size:1.65rem; line-height:1;
      font-weight:850; letter-spacing:.04em; margin-top:.6rem; }
    .status-explanation { color:#a4b1c2; font-size:.78rem; line-height:1.5; margin-top:.55rem; }
    .panel-heading { display:flex; align-items:flex-start; justify-content:space-between;
      gap:.75rem; margin-bottom:.25rem; }
    .live-label { color:#8796aa; font-size:.66rem; text-transform:uppercase;
      letter-spacing:.08em; white-space:nowrap; }
    .live-grid { display:grid; grid-template-columns:1fr auto; gap:.82rem .75rem; margin-top:1rem; }
    .live-key { color:#91a0b5; font-size:.75rem; }
    .live-value { color:#edf3fb; font-size:.78rem; font-weight:700; text-align:right; }
    .live-value.status-safe { color:#37d39a; }
    .live-value.status-caution { color:#f5b84b; }
    .live-value.status-danger { color:#ff6673; }
    .live-value.status-stale, .live-value.status-waiting { color:#f5b84b; }
    .live-value.status-disconnected { color:#91a0b5; }
    .chart-panel, .live-panel { min-height:330px; }
    .chart-caption { color:#718198; font-size:.68rem; margin-top:-.25rem; }
    .safety-note { color:#758399; font-size:.67rem; line-height:1.5; margin:.9rem .1rem 0; }
    @media (max-width: 1050px) {
      .metric-card { padding:.85rem; }
      .metric-value { font-size:1.55rem; }
      .metric-label { font-size:.66rem; }
    }
    @media (max-width: 700px) {
      .block-container { padding-top:.8rem; }
      .wordmark { font-size:1.45rem; }
      .brand-mark { width:40px; height:40px; }
      .device-pill { padding:.45rem .6rem; font-size:.61rem; }
      .metric-card { min-height:128px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


_initial_speed, _initial_distance = preset_values("SAFE")
st.session_state.setdefault("scenario", "SAFE")
st.session_state.setdefault("simulated_speed", _initial_speed)
st.session_state.setdefault("obstacle_distance", _initial_distance)
st.session_state.setdefault("mode_selection", "Demo Mode")
st.session_state.setdefault("active_mode", "Demo Mode")
if "demo_source" not in st.session_state:
    st.session_state.demo_source = DemoDataSource()
st.session_state.setdefault("hardware_source", None)
st.session_state.setdefault("hardware_error", None)
st.session_state.setdefault("serial_port", "")
st.session_state.setdefault("serial_port_choice", "Enter manually")
st.session_state.setdefault("manual_serial_port", "COM3")
st.session_state.setdefault("reading_history", [])
st.session_state.setdefault("last_history_timestamp", None)


with st.sidebar:
    st.markdown("### Data source")
    st.selectbox("Operating mode", ["Demo Mode", "Hardware Mode"], key="mode_selection")
    if st.session_state.mode_selection != st.session_state.active_mode:
        source = st.session_state.hardware_source
        if source is not None:
            source.disconnect()
        st.session_state.hardware_source = None
        st.session_state.hardware_error = None
        st.session_state.active_mode = st.session_state.mode_selection
        st.session_state.reading_history = []
        st.session_state.last_history_timestamp = None

    if st.session_state.mode_selection == "Demo Mode":
        st.markdown(
            '<div class="device-pill"><span class="device-dot"></span>DEMO MODE · SIMULATED</div>',
            unsafe_allow_html=True,
        )
        st.caption("No hardware measurements are used in Demo Mode.")
        st.selectbox(
            "Risk scenario",
            ["SAFE", "CAUTION", "DANGER"],
            key="scenario",
            on_change=apply_preset,
            help="Presets use obstacle distances matching the ESP32 LED thresholds.",
        )
        st.slider(
            "Simulated speed (km/h)",
            min_value=0.0,
            max_value=160.0,
            step=1.0,
            key="simulated_speed",
        )
        st.slider(
            "Obstacle distance (m)",
            min_value=0.0,
            max_value=250.0,
            step=0.1,
            key="obstacle_distance",
        )
    else:
        st.markdown(
            '<div class="device-pill"><span class="device-dot disconnected"></span>HARDWARE MODE</div>',
            unsafe_allow_html=True,
        )
        st.caption("USB serial · ESP32-C6 protocol: newline-delimited JSON · 115200 baud")
        if st.button("Refresh serial ports", use_container_width=True):
            st.rerun()
        try:
            available_ports = list_serial_ports()
        except (OSError, ImportError) as error:
            available_ports = []
            st.session_state.hardware_error = f"Could not enumerate serial ports: {error}"
        if not available_ports:
            st.info("Windows has not listed a serial port. You can still enter its COM name below.")
        port_options = [*available_ports, "Enter manually"]
        if st.session_state.serial_port_choice not in port_options:
            st.session_state.serial_port_choice = (
                available_ports[0] if available_ports else "Enter manually"
            )
        st.selectbox("Available serial ports", port_options, key="serial_port_choice")
        if st.session_state.serial_port_choice == "Enter manually":
            if not st.session_state.manual_serial_port:
                st.session_state.manual_serial_port = "COM3"
            st.text_input(
                "COM port name",
                key="manual_serial_port",
                placeholder="e.g. COM5",
                help="Find the COM number in Windows Device Manager under Ports (COM & LPT).",
            )
            selected_port = st.session_state.manual_serial_port.strip()
        else:
            selected_port = st.session_state.serial_port_choice
        st.session_state.serial_port = selected_port

        current_source = st.session_state.hardware_source
        if (
            current_source is not None
            and current_source.is_connected
            and current_source.port != selected_port
        ):
            current_source.disconnect()
            st.session_state.hardware_source = None
        if st.session_state.hardware_source is not None and st.session_state.hardware_source.is_connected:
            if st.button("Disconnect", use_container_width=True):
                st.session_state.hardware_source.disconnect()
                st.session_state.hardware_source = None
                st.session_state.hardware_error = None
                st.rerun()
        elif st.button(
            "Connect",
            use_container_width=True,
            disabled=not selected_port,
        ):
            source = HardwareDataSource(port=selected_port, baudrate=115200)
            if source.connect():
                st.session_state.hardware_source = source
                st.session_state.hardware_error = None
            else:
                st.session_state.hardware_source = None
                st.session_state.hardware_error = (
                    source.last_error or f"Could not open {selected_port}."
                )
        if st.session_state.hardware_error:
            st.error(st.session_state.hardware_error)

    st.divider()
    st.markdown("**Demonstration assumptions (not verified vehicle characteristics)**")
    st.caption(
        f"Reaction time: {DEFAULT_CONFIG.reaction_time_s:.1f} s  \n"
        f"Braking deceleration: {DEFAULT_CONFIG.braking_deceleration_mps2:.1f} m/s²  \n"
        f"Safety buffer: {DEFAULT_CONFIG.safety_buffer_m:.1f} m  \n"
        f"DANGER: ≤ {DEFAULT_DANGER_DISTANCE_M:.2f} m · "
        f"CAUTION: > {DEFAULT_DANGER_DISTANCE_M:.2f} to "
        f"≤ {DEFAULT_CAUTION_DISTANCE_M:.2f} m · "
        f"SAFE: > {DEFAULT_CAUTION_DISTANCE_M:.2f} m"
    )


STATUS_ICONS = {
    "SAFE": """
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        <path d="m8.5 12 2.3 2.3 4.8-4.8"/>
      </svg>
    """,
    "CAUTION": """
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M10.3 3.9 2.6 17.2A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.8L13.7 3.9a2 2 0 0 0-3.4 0z"/>
        <path d="M12 9v4m0 3h.01"/>
      </svg>
    """,
    "DANGER": """
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        <path d="m9 9 6 6m0-6-6 6"/>
      </svg>
    """,
    "WAITING": """
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>
      </svg>
    """,
    "STALE": """
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>
      </svg>
    """,
    "DISCONNECTED": """
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M10 13a5 5 0 0 0 7.1 0l3-3a5 5 0 0 0-7.1-7.1l-1.7 1.7"/>
        <path d="M14 11a5 5 0 0 0-7.1 0l-3 3A5 5 0 0 0 11 21l1.7-1.7"/>
        <path d="m3 3 18 18"/>
      </svg>
    """,
}


@st.fragment(run_every=0.5)
def render_dashboard() -> None:
    """Refresh displayed hardware data without blocking the Streamlit UI."""
    hardware_mode = st.session_state.mode_selection == "Hardware Mode"
    hardware_source = st.session_state.hardware_source if hardware_mode else None
    if hardware_mode and hardware_source is not None:
        reading = hardware_source.read()
        port_open = hardware_source.is_connected
        if not port_open:
            connection_text = "USB SERIAL · DISCONNECTED"
            connection_class = "disconnected"
        elif reading.stale:
            connection_text = f"USB SERIAL · DATA STALE · {hardware_source.port}"
            connection_class = "stale"
        elif not reading.valid:
            connection_text = "USB SERIAL · PORT OPEN · WAITING FOR DATA"
            connection_class = "waiting"
        else:
            connection_text = f"USB SERIAL · PORT OPEN · {hardware_source.port}"
            connection_class = "connected"
            if reading.error:
                connection_text += " · MESSAGE ERROR"
                connection_class = "waiting"
    elif hardware_mode:
        reading = SensorReading(
            None,
            None,
            0.0,
            "hardware",
            False,
            error=st.session_state.hardware_error
            or "Serial port is disconnected. Choose a port and connect.",
        )
        connection_text = "USB SERIAL · DISCONNECTED"
        connection_class = "disconnected"
    else:
        demo_source: DemoDataSource = st.session_state.demo_source
        demo_source.set_values(
            obstacle_distance_m=st.session_state.obstacle_distance,
            speed_kmh=st.session_state.simulated_speed,
        )
        reading = demo_source.read()
        connection_text = "DEMO SIMULATOR · SIMULATED"
        connection_class = "demo"

    valid_reading = sensor_data_status(reading) == "AVAILABLE"
    current = None
    if (
        valid_reading
        and reading.obstacle_distance_m is not None
        and reading.speed_kmh is not None
    ):
        try:
            current = compute_all(
                obstacle_distance_m=float(reading.obstacle_distance_m),
                speed_kmh=float(reading.speed_kmh),
            )
        except PredictionError as error:
            st.error(f"Unable to calculate the current prediction: {error}")

    if current is not None:
        obstacle_distance = current["obstacle_distance_m"]
        speed_kmh = current["speed_kmh"]
        reaction_distance = current["reaction_distance_m"]
        braking_distance = current["braking_distance_m"]
        stopping_distance = current["stopping_distance_m"]
        safety_margin = current["safety_margin_m"]
        status = current["status"]
        explanation = current["explanation"]
        status_color = STATUS_COLORS[status]
    else:
        obstacle_distance = None
        speed_kmh = None
        reaction_distance = None
        braking_distance = None
        stopping_distance = None
        safety_margin = None
        status = "SENSOR DATA UNAVAILABLE"
        if reading.stale:
            explanation = "The latest valid sensor reading is older than 2.5 seconds."
        elif not (hardware_source and hardware_source.is_connected) and hardware_mode:
            explanation = "The serial port is disconnected; no current hardware reading is available."
        elif reading.error:
            explanation = "The latest sensor message is invalid or reports a sensor error."
        else:
            explanation = "Waiting for the first valid, fresh sensor reading."
        status_color = COLORS["muted"]

    latest_timestamp = (
        datetime.fromtimestamp(reading.timestamp)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        if valid_reading
        else "Unavailable"
    )
    if current is not None and reading.timestamp != st.session_state.last_history_timestamp:
        st.session_state.reading_history.append(
            {
                "timestamp": reading.timestamp,
                "obstacle_distance_m": current["obstacle_distance_m"],
                "stopping_distance_m": current["stopping_distance_m"],
                "safety_margin_m": current["safety_margin_m"],
            }
        )
        del st.session_state.reading_history[:-300]
        st.session_state.last_history_timestamp = reading.timestamp

    st.markdown(
        f"""
    <div class="dashboard-header">
      <div class="brand">
        <div class="brand-mark">{CAR_ICON}</div>
        <div>
          <div class="wordmark">Brake<span>Margin</span></div>
          <div class="tagline">Predictive Braking Safety System</div>
        </div>
      </div>
      <div class="device-pill {connection_class}"><span class="device-dot {connection_class}"></span>{connection_text}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if reading.error and (
        reading.stale or not reading.valid or (hardware_source and hardware_source.last_error)
    ):
        st.warning(reading.error)
    if not valid_reading:
        st.error("SENSOR DATA UNAVAILABLE")

    speed_label = "SIMULATED SPEED" if reading.source == "demo" else "MEASURED SPEED"
    distance_subtitle = "Simulated distance ahead" if reading.source == "demo" else "Hardware sensor reading"
    speed_subtitle = "Demo vehicle speed" if reading.source == "demo" else "Hardware sensor reading"
    metric_distance = f"{obstacle_distance:.1f}" if obstacle_distance is not None else "—"
    metric_speed = f"{speed_kmh:.1f}" if speed_kmh is not None else "—"
    metric_reaction = f"{reaction_distance:.1f}" if reaction_distance is not None else "—"
    metric_braking = f"{braking_distance:.1f}" if braking_distance is not None else "—"
    metric_stopping = f"{stopping_distance:.1f}" if stopping_distance is not None else "—"
    metric_margin = f"{safety_margin:+.1f}" if safety_margin is not None else "—"
    margin_subtitle = (
        "Obstacle distance less estimate"
        if safety_margin is not None
        else "Waiting for fresh valid sensor data"
    )

    status_icon = STATUS_ICONS.get(status, STATUS_ICONS["WAITING"])
    metric_columns = st.columns(4, gap="medium")
    with metric_columns[0]:
        render_metric(
            "OBSTACLE DISTANCE",
            metric_distance,
            "m",
            distance_subtitle,
            METRIC_ICONS["distance"],
            COLORS["blue"],
        )
    with metric_columns[1]:
        render_metric(
            speed_label,
            metric_speed,
            "km/h",
            speed_subtitle,
            METRIC_ICONS["speed"],
            COLORS["blue"],
        )
    with metric_columns[2]:
        render_metric("REACTION DISTANCE", metric_reaction, "m", "Estimated at 1.5 s", METRIC_ICONS["brake"], "#dbe5f1")
    with metric_columns[3]:
        render_metric("BRAKING DISTANCE", metric_braking, "m", "Estimated at 5.0 m/s²", METRIC_ICONS["brake"], "#dbe5f1")

    metric_columns = st.columns(3, gap="medium")
    with metric_columns[0]:
        render_metric(
            "TOTAL STOPPING DISTANCE",
            metric_stopping,
            "m",
            "Estimated reaction + braking",
            METRIC_ICONS["brake"],
            "#dbe5f1",
        )
    with metric_columns[1]:
        render_metric(
            "SAFETY MARGIN",
            metric_margin,
            "m",
            margin_subtitle,
            METRIC_ICONS["margin"],
            status_color,
        )
    with metric_columns[2]:
        render_metric(
            "CURRENT RISK STATUS",
            status,
            "",
            "Based on obstacle distance · matches ESP32 LEDs",
            status_icon,
            status_color,
        )

    with st.container(border=True):
        safety_columns = st.columns([2.35, 1], gap="medium", vertical_alignment="center")
        with safety_columns[0]:
            st.markdown(
                """
                <div class="section-kicker">Distance visualization</div>
                <div class="safety-title">Vehicle approach & estimated stopping point</div>
                <div class="safety-subtitle">Illustrative geometry · values reflect the current data source</div>
                """,
                unsafe_allow_html=True,
            )
            if (
                valid_reading
                and obstacle_distance is not None
                and stopping_distance is not None
            ):
                illustration = create_road_illustration(
                    obstacle_distance,
                    stopping_distance,
                    status,
                )
            else:
                illustration = """
                <svg viewBox="0 0 800 210" role="img" aria-label="Waiting for fresh sensor data">
                  <path d="M36 151H764M46 168H754" stroke="#2a374b" stroke-width="3"/>
                  <g transform="translate(95 102)" fill="#17283e" stroke="#4b9bff" stroke-width="2">
                    <path d="M7 25 16 6q3-6 10-6h43q7 0 11 6l12 19v22H7z"/>
                    <circle cx="26" cy="47" r="8" fill="#080d17"/>
                    <circle cx="72" cy="47" r="8" fill="#080d17"/>
                  </g>
                  <path d="M730 100v51m-14-41h29m-29 13h29m-29 13h29" stroke="#ff6673" stroke-width="4"/>
                  <text x="400" y="75" text-anchor="middle" fill="#91a0b5" font-size="14"
                        font-family="Segoe UI, sans-serif">Waiting for fresh sensor data</text>
                </svg>
                """
            st.markdown(
                f'<div class="road-illustration">{illustration}</div>',
                unsafe_allow_html=True,
            )
        with safety_columns[1]:
            st.markdown(
                f"""
                <div class="status-card" style="--status-accent:{status_color}">
                  <div class="status-icon">{status_icon}</div>
                  <div class="status-name">{status}</div>
                  <div class="status-explanation">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(f"Latest reading: {latest_timestamp}")

    st.markdown("")
    distance_history_chart, margin_history_chart = create_history_charts(
        st.session_state.reading_history
    )
    chart_columns = st.columns(2, gap="medium")
    with chart_columns[0], st.container(border=True):
        st.markdown(
            """
              <div class="panel-heading">
                <div>
                  <div class="section-kicker">Live time series · latest 300 valid readings</div>
                  <div class="safety-title">Obstacle & Stopping Distance</div>
                </div>
              </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            distance_history_chart,
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True},
        )
    with chart_columns[1], st.container(border=True):
        st.markdown(
            """
              <div class="panel-heading">
                <div>
                  <div class="section-kicker">Live time series · latest 300 valid readings</div>
                  <div class="safety-title">Safety Margin</div>
                </div>
              </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            margin_history_chart,
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True},
        )

    st.markdown(
        """
        <div class="safety-note">
          Prototype demonstration only. Stopping distances are estimates based on stated model assumptions;
          this system is not certified and must not be used to make real-road safety decisions.
        </div>
        """,
        unsafe_allow_html=True,
    )


render_dashboard()
