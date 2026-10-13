from __future__ import annotations

import io
import time
from collections import deque

import pandas as pd
import streamlit as st

from src.data_collector import MeasurementStream
from src.movement_detector import MovementDetector
from src.visualizations import make_radar, make_signal_chart


st.set_page_config(page_title="Wi-Fi Radar", page_icon="📡", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
    .stApp { background: #07101c; color: #e6edf6; }
    [data-testid="stSidebar"] { background: #0b1625; border-right: 1px solid #1c2b3d; }
    [data-testid="stMetric"] { background: #0d1a2a; border: 1px solid #1c3046; padding: 14px 16px; border-radius: 12px; }
    [data-testid="stMetricLabel"] { color: #8ea3ba; }
    h1, h2, h3 { letter-spacing: -0.025em; }
    .status-box { border-radius: 12px; padding: 16px 18px; font-weight: 700; letter-spacing: .06em; }
    .status-idle { color: #aebdd0; background: #111f30; border: 1px solid #263c53; }
    .status-ready { color: #34e2c2; background: #0b2729; border: 1px solid #1d655c; }
    .status-motion { color: #ffcb75; background: #302315; border: 1px solid #9b6727; }
    .hint { color: #8ea3ba; font-size: .86rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_state() -> None:
    defaults = {
        "stream": MeasurementStream(),
        "records": deque(maxlen=1500),
        "detector": MovementDetector(),
        "selected_mode": "CSI amplitude",
        "calibrating": False,
        "calibration_values": [],
        "calibration_message": "Baseline not calibrated",
        "event_count": 0,
        "movement_seconds": 0.0,
        "last_sample_time": None,
        "last_detection": None,
        "session_packets": 0,
        "session_started": None,
        "last_valid_time": None,
        "last_value": None,
        "last_rssi": None,
        "last_metric": "CSI amplitude",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_state()
stream: MeasurementStream = st.session_state.stream


def reset_session() -> None:
    st.session_state.records.clear()
    st.session_state.detector.reset()
    st.session_state.calibrating = False
    st.session_state.calibration_values = []
    st.session_state.calibration_message = "Baseline not calibrated"
    st.session_state.event_count = 0
    st.session_state.movement_seconds = 0.0
    st.session_state.last_sample_time = None
    st.session_state.last_detection = None
    st.session_state.session_packets = 0
    st.session_state.session_started = time.time()
    st.session_state.last_valid_time = None
    st.session_state.last_value = None
    st.session_state.last_rssi = None


st.title("📡 Wi-Fi Radar")
st.caption("Device-free movement sensing from changes in Wi-Fi channel measurements")

with st.sidebar:
    st.header("Sensor controls")
    source = st.selectbox("Input source", ["Demo simulation", "ESP32 serial"], key="source_choice")
    if source == "ESP32 serial":
        port = st.text_input("Serial port", value="/dev/ttyUSB0", help="Common Linux ports: /dev/ttyUSB0 or /dev/ttyACM0")
        baud = st.number_input("Baud rate", min_value=9600, max_value=921600, value=115200, step=9600)
    else:
        port, baud = "", 115200
    selected_mode = st.radio("Signal metric", ["CSI amplitude", "RSSI"], key="metric_choice")
    st.session_state.selected_mode = selected_mode
    sensitivity = st.slider("Detection sensitivity", min_value=1.5, max_value=6.0, value=3.0, step=0.25)
    st.session_state.detector.sensitivity = sensitivity
    st.session_state.detector.noise_floor = 2.0 if selected_mode == "RSSI" else 0.5
    st.caption("Lower values detect smaller changes and can increase false alarms.")

    left, right = st.columns(2)
    with left:
        if st.button("Start monitoring", type="primary", use_container_width=True):
            reset_session()
            stream.start(source, port=port, baud=int(baud))
            st.rerun()
    with right:
        if st.button("Stop", use_container_width=True):
            stream.stop()
            st.rerun()

    if st.button("Calibrate baseline", use_container_width=True, disabled=not stream.running):
        st.session_state.detector.reset()
        st.session_state.calibration_values = []
        st.session_state.calibrating = True
        st.session_state.calibration_message = "Calibration started: stay still for 4 seconds"
        st.session_state.last_detection = None
        st.session_state.last_sample_time = None
        st.rerun()
    st.markdown("<div class='hint'>Calibration uses the next 40 valid samples. Stand still while they are collected.</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Mode labels**")
    st.caption("CSI amplitude: derived from received complex subcarriers. RSSI: link power only; less sensitive and more affected by distance/interference.")

if st.session_state.last_metric != selected_mode:
    st.session_state.detector.reset()
    st.session_state.records.clear()
    st.session_state.calibrating = False
    st.session_state.calibration_values = []
    st.session_state.calibration_message = "Signal metric changed; calibrate a new baseline"
    st.session_state.event_count = 0
    st.session_state.movement_seconds = 0.0
    st.session_state.last_sample_time = None
    st.session_state.last_detection = None
    st.session_state.last_valid_time = None
    st.session_state.last_value = None
    st.session_state.last_metric = selected_mode


def render_live_panel() -> None:
    stream: MeasurementStream = st.session_state.stream
    detector: MovementDetector = st.session_state.detector
    selected = st.session_state.selected_mode
    samples = stream.read_available()
    st.session_state.session_packets += len(samples)
    now = time.time()

    for sample in samples:
        selected_value = sample.value_for(selected)
        if sample.rssi_dbm is not None:
            st.session_state.last_rssi = sample.rssi_dbm
        if selected_value is None:
            # RSSI-only fallback firmware cannot provide CSI amplitude.
            st.session_state.records.append(
                {"timestamp": sample.timestamp, "mode": sample.mode, "sequence": sample.sequence,
                 "amplitude": sample.amplitude, "rssi_dbm": sample.rssi_dbm,
                 "value": None, "baseline": None, "threshold": None, "moving": False}
            )
            continue

        timestamp = sample.timestamp
        if st.session_state.calibrating:
            st.session_state.calibration_values.append(float(selected_value))
            if len(st.session_state.calibration_values) >= 40:
                baseline = detector.calibrate(st.session_state.calibration_values)
                st.session_state.calibrating = False
                st.session_state.calibration_message = (
                    f"Baseline ready · median {baseline.center:.2f} · spread {baseline.spread:.2f}"
                )
            st.session_state.records.append(
                {"timestamp": timestamp, "mode": sample.mode, "sequence": sample.sequence,
                 "amplitude": sample.amplitude, "rssi_dbm": sample.rssi_dbm,
                 "value": float(selected_value), "baseline": None, "threshold": None, "moving": False}
            )
            st.session_state.last_valid_time = timestamp
            st.session_state.last_value = float(selected_value)
            continue

        detection = detector.update(float(selected_value))
        previous_time = st.session_state.last_sample_time
        previous_detection = st.session_state.last_detection
        if previous_time is not None and previous_detection and previous_detection.moving:
            st.session_state.movement_seconds += min(max(timestamp - previous_time, 0.0), 1.0)
        if detection.event_started:
            st.session_state.event_count += 1
        st.session_state.last_sample_time = timestamp
        st.session_state.last_detection = detection
        st.session_state.last_valid_time = timestamp
        st.session_state.last_value = float(selected_value)
        st.session_state.records.append(
            {"timestamp": timestamp, "mode": sample.mode, "sequence": sample.sequence,
             "amplitude": sample.amplitude, "rssi_dbm": sample.rssi_dbm,
             "value": detection.filtered_value,
             "baseline": detector.baseline.center if detector.baseline else None,
             "threshold": detection.threshold, "moving": detection.moving}
        )

    records = list(st.session_state.records)
    valid = [row for row in records if row.get("value") is not None]
    recent = valid[-120:]
    detection = st.session_state.last_detection
    has_baseline = detector.baseline is not None
    stale = st.session_state.last_valid_time is None or now - st.session_state.last_valid_time > 3.0
    if st.session_state.calibrating and not stream.running:
        st.session_state.calibrating = False
        st.session_state.calibration_message = "Calibration stopped because the sensor is disconnected"
    if st.session_state.calibrating:
        status = "CALIBRATING"
    elif not stream.running:
        status = "MONITORING STOPPED"
    elif stale or not stream.connected:
        status = "WAITING FOR DATA"
    elif not has_baseline:
        status = "CALIBRATE BASELINE"
    elif detection and detection.moving:
        status = "MOVEMENT DETECTED"
    else:
        status = "NO MOVEMENT"
    status_class = "status-motion" if status == "MOVEMENT DETECTED" else ("status-ready" if status == "NO MOVEMENT" else "status-idle")
    st.markdown(f"<div class='status-box {status_class}'>● &nbsp; {status}</div>", unsafe_allow_html=True)
    if stream.error:
        st.error(stream.error)
    elif source_is_rssi_only(records) and selected == "CSI amplitude":
        st.info("RSSI-only measurements are arriving. Select RSSI in the sidebar to process this fallback stream.")
    elif st.session_state.calibration_message:
        st.caption(st.session_state.calibration_message)

    quality, link = signal_quality(st.session_state.last_rssi, stream)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Movement events", st.session_state.event_count)
    m2.metric("Time detecting movement", f"{st.session_state.movement_seconds:.1f} s")
    m3.metric("Received packets", st.session_state.session_packets)
    m4.metric("Signal quality", quality)
    st.caption(f"Sensor: {link} · {stream.source or 'Not started'} · Data age: {age_label(st.session_state.last_valid_time)}")

    chart_col, radar_col = st.columns([1.55, 1])
    with chart_col:
        baseline_center = detector.baseline.center if detector.baseline else None
        threshold = detection.threshold if detection and detection.threshold is not None else None
        chart_points = [{"timestamp": row["timestamp"], "value": row["value"]} for row in recent]
        st.pyplot(make_signal_chart(chart_points, selected_mode=selected, baseline=baseline_center,
                                    threshold=threshold, moving=bool(detection and detection.moving)),
                  use_container_width=True)
    with radar_col:
        st.pyplot(make_radar(moving=bool(detection and detection.moving), event_count=st.session_state.event_count),
                  use_container_width=True)

    if st.session_state.calibrating:
        st.progress(min(len(st.session_state.calibration_values) / 40.0, 1.0),
                    text=f"Baseline calibration: {len(st.session_state.calibration_values)}/40 samples")
    st.caption("Radar sweep and marker are illustrative. The prototype detects channel changes; it does not estimate a person's position.")

    export = pd.DataFrame(records)
    if not export.empty:
        buffer = io.StringIO()
        export.to_csv(buffer, index=False)
        st.download_button("Export session as CSV", buffer.getvalue(), file_name="wifi_radar_session.csv",
                           mime="text/csv", use_container_width=False)
    else:
        st.download_button("Export session as CSV", "timestamp,mode,sequence,amplitude,rssi_dbm,value,baseline,threshold,moving\n",
                           file_name="wifi_radar_session.csv", mime="text/csv", disabled=True)


def source_is_rssi_only(records: list[dict]) -> bool:
    usable = [row for row in records if row.get("rssi_dbm") is not None]
    return bool(usable) and all(row.get("amplitude") is None for row in usable[-30:])


def signal_quality(rssi: float | None, stream: MeasurementStream) -> tuple[str, str]:
    if not stream.running and not stream.connected:
        return "—", "Stopped"
    if not stream.connected:
        return "No link", "Connecting / disconnected"
    if rssi is None:
        return "Unknown", "Connected"
    if rssi >= -55:
        return "Strong", "Connected"
    if rssi >= -67:
        return "Good", "Connected"
    if rssi >= -75:
        return "Fair", "Connected"
    return "Weak", "Connected"


def age_label(timestamp: float | None) -> str:
    if timestamp is None:
        return "—"
    age = max(0.0, time.time() - timestamp)
    return f"{age:.1f} s" if age < 10 else ">10 s"


@st.fragment(run_every="500ms")
def live_panel() -> None:
    render_live_panel()


live_panel()
