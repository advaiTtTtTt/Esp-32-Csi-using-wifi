"""Small, explainable signal-processing helpers used by the motion detector."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from scipy.ndimage import median_filter as _scipy_median_filter
    from scipy.stats import median_abs_deviation as _scipy_mad
except ImportError:  # Keep the algorithm testable before optional packages are installed.
    _scipy_median_filter = None
    _scipy_mad = None


def filter_signal(values: list[float] | np.ndarray, window: int = 5) -> np.ndarray:
    """Return a median-filtered 1-D signal, preserving the input length."""
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError("signal must be one-dimensional")
    if window < 1:
        raise ValueError("window must be at least 1")
    if array.size == 0:
        return array.copy()
    if window % 2 == 0:
        window += 1
    if _scipy_median_filter is not None:
        return _scipy_median_filter(array, size=window, mode="nearest")
    radius = window // 2
    padded = np.pad(array, (radius, radius), mode="edge")
    return np.asarray([np.median(padded[index : index + window]) for index in range(array.size)])


@dataclass(frozen=True)
class Baseline:
    center: float
    spread: float
    samples: int


def calculate_baseline(values: list[float] | np.ndarray) -> Baseline:
    """Use the median and scaled MAD to resist outliers during calibration."""
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size < 5:
        raise ValueError("at least 5 valid samples are required for calibration")
    center = float(np.median(array))
    if _scipy_mad is not None:
        spread = float(_scipy_mad(array, scale="normal"))
    else:
        spread = float(np.median(np.abs(array - center)) / 0.6744897501960817)
    if not np.isfinite(spread):
        spread = 0.0
    return Baseline(center=center, spread=spread, samples=int(array.size))
