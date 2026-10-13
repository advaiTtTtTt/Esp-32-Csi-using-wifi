"""Baseline-calibrated movement detection with filtering and persistence."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from .signal_processing import Baseline, calculate_baseline


@dataclass(frozen=True)
class Detection:
    value: float
    filtered_value: float
    deviation: float
    threshold: float | None
    moving: bool
    event_started: bool
    baseline_ready: bool


class MovementDetector:
    """Detect sustained deviations from a stationary-room baseline.

    ``sensitivity`` is the number of robust baseline spreads a sample must
    exceed. A small absolute floor avoids zero thresholds on very quiet data.
    No confidence score is produced: this threshold detector is not calibrated
    to support a probabilistic confidence claim.
    """

    def __init__(
        self,
        *,
        sensitivity: float = 3.0,
        filter_window: int = 5,
        persistence: int = 3,
        release_samples: int = 5,
        noise_floor: float = 0.5,
    ) -> None:
        if sensitivity <= 0:
            raise ValueError("sensitivity must be positive")
        if persistence < 1 or release_samples < 1:
            raise ValueError("persistence and release_samples must be positive")
        self.sensitivity = float(sensitivity)
        self.filter_window = max(1, int(filter_window))
        self.persistence = int(persistence)
        self.release_samples = int(release_samples)
        self.noise_floor = float(noise_floor)
        self._values: deque[float] = deque(maxlen=self.filter_window)
        self.baseline: Baseline | None = None
        self.moving = False
        self._high_count = 0
        self._low_count = 0

    def reset(self) -> None:
        self._values.clear()
        self.baseline = None
        self.moving = False
        self._high_count = 0
        self._low_count = 0

    def calibrate(self, values: list[float]) -> Baseline:
        self.baseline = calculate_baseline(values)
        self._values.clear()
        self.moving = False
        self._high_count = 0
        self._low_count = 0
        return self.baseline

    def update(self, value: float) -> Detection:
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("measurement must be finite")
        self._values.append(number)
        filtered = float(np.median(self._values))
        if self.baseline is None:
            return Detection(number, filtered, 0.0, None, False, False, False)

        deviation = abs(filtered - self.baseline.center)
        threshold = max(self.sensitivity * self.baseline.spread, self.noise_floor)
        event_started = False
        if deviation > threshold:
            self._high_count += 1
            self._low_count = 0
            if not self.moving and self._high_count >= self.persistence:
                self.moving = True
                event_started = True
        else:
            self._high_count = 0
            if self.moving:
                self._low_count += 1
                if self._low_count >= self.release_samples:
                    self.moving = False
                    self._low_count = 0
        return Detection(
            value=number,
            filtered_value=filtered,
            deviation=deviation,
            threshold=threshold,
            moving=self.moving,
            event_started=event_started,
            baseline_ready=True,
        )
