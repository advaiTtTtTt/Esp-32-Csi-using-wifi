"""Background measurement sources for simulated and ESP32 serial data."""

from __future__ import annotations

import json
import math
import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Measurement:
    timestamp: float
    mode: str
    sequence: int | None = None
    amplitude: float | None = None
    rssi_dbm: float | None = None
    device_time_us: int | None = None

    def value_for(self, selected_mode: str) -> float | None:
        if selected_mode == "CSI amplitude":
            return self.amplitude
        return self.rssi_dbm


def parse_serial_line(line: str) -> Measurement | None:
    """Parse one firmware JSON line; malformed and non-data lines are ignored."""
    try:
        payload: Any = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("type") not in {"csi", "rssi"}:
        return None
    try:
        sequence = int(payload["seq"]) if payload.get("seq") is not None else None
        rssi = float(payload["rssi_dbm"]) if payload.get("rssi_dbm") is not None else None
        amplitude = float(payload["amplitude"]) if payload.get("amplitude") is not None else None
        device_time = int(payload["t_us"]) if payload.get("t_us") is not None else None
    except (TypeError, ValueError, OverflowError):
        return None
    numeric = [item for item in (rssi, amplitude) if item is not None]
    if not numeric or not all(math.isfinite(item) for item in numeric):
        return None
    if payload["type"] == "csi" and amplitude is None:
        return None
    if payload["type"] == "rssi" and rssi is None:
        return None
    return Measurement(
        timestamp=time.time(),
        mode=str(payload["type"]),
        sequence=sequence,
        amplitude=amplitude,
        rssi_dbm=rssi,
        device_time_us=device_time,
    )


class MeasurementStream:
    """Owns a producer thread and exposes a bounded queue to the dashboard."""

    def __init__(self, queue_size: int = 2000) -> None:
        self.samples: queue.Queue[Measurement] = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.running = False
        self.connected = False
        self.source = ""
        self.error = ""
        self.dropped = 0

    def start(self, source: str, *, port: str = "", baud: int = 115200) -> None:
        self.stop()
        while True:
            try:
                self.samples.get_nowait()
            except queue.Empty:
                break
        self._stop = threading.Event()
        self.source = source
        self.error = ""
        self.connected = False
        self.running = True
        target = self._simulate if source == "Demo simulation" else self._read_serial
        kwargs = {} if source == "Demo simulation" else {"port": port, "baud": baud}
        self._thread = threading.Thread(target=target, kwargs=kwargs, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self.running = False
        self.connected = False

    def read_available(self, limit: int = 1000) -> list[Measurement]:
        result: list[Measurement] = []
        for _ in range(limit):
            try:
                result.append(self.samples.get_nowait())
            except queue.Empty:
                break
        return result

    def _put(self, sample: Measurement) -> None:
        try:
            self.samples.put_nowait(sample)
        except queue.Full:
            try:
                self.samples.get_nowait()
            except queue.Empty:
                pass
            self.dropped += 1
            try:
                self.samples.put_nowait(sample)
            except queue.Full:
                self.dropped += 1

    def _simulate(self) -> None:
        self.connected = True
        start = time.monotonic()
        sequence = 0
        rng = random.Random()
        while not self._stop.is_set():
            elapsed = time.monotonic() - start
            phase = elapsed % 16.0
            moving = 4.0 <= phase <= 8.0 or 12.0 <= phase <= 13.7
            pulse = (18.0 + 7.0 * math.sin(2 * math.pi * elapsed * 0.7)) if moving else 0.0
            amplitude = 100.0 + pulse + rng.gauss(0.0, 1.5)
            rssi = -54.0 + (2.2 if moving else 0.0) + rng.gauss(0.0, 0.8)
            self._put(Measurement(time.time(), "demo", sequence, amplitude, rssi))
            sequence += 1
            self._stop.wait(0.1)
        self.connected = False
        self.running = False

    def _read_serial(self, *, port: str, baud: int) -> None:
        try:
            import serial  # Imported only when hardware mode is selected.

            with serial.Serial(port=port, baudrate=baud, timeout=0.5) as connection:
                connection.reset_input_buffer()
                self.connected = True
                while not self._stop.is_set():
                    try:
                        raw = connection.readline()
                    except (serial.SerialException, OSError) as error:
                        self.error = f"Serial read failed: {error}"
                        break
                    if not raw:
                        continue
                    sample = parse_serial_line(raw.decode("utf-8", errors="replace").strip())
                    if sample is not None:
                        self._put(sample)
        except Exception as error:  # Keep Streamlit alive and surface the cause.
            self.error = f"Could not open {port or 'serial port'}: {error}"
        finally:
            self.connected = False
            self.running = False

