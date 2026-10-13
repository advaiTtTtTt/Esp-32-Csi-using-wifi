"""Dark, radar-inspired Matplotlib visuals for the Streamlit dashboard."""

from __future__ import annotations

import math
import time
from collections.abc import Sequence

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Wedge


BG = "#08111f"
GRID = "#18304a"
TEAL = "#34e2c2"
AMBER = "#ffbd59"
TEXT = "#b8c7d9"


def make_signal_chart(
    points: Sequence[dict[str, float]],
    *,
    selected_mode: str,
    baseline: float | None,
    threshold: float | None,
    moving: bool,
) -> Figure:
    fig = Figure(figsize=(8.2, 3.15), dpi=110, facecolor=BG)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_facecolor(BG)
    if points:
        x = np.array([point["timestamp"] for point in points], dtype=float)
        x -= x[-1]
        y = np.array([point["value"] for point in points], dtype=float)
        ax.plot(x, y, color=AMBER if moving else TEAL, linewidth=1.8)
        ax.fill_between(x, y, np.nanmin(y), color=AMBER if moving else TEAL, alpha=0.08)
        if baseline is not None:
            ax.axhline(baseline, color="#71839b", linestyle="--", linewidth=1, label="Baseline")
            if threshold is not None:
                ax.axhline(baseline + threshold, color="#526980", linestyle=":", linewidth=0.9)
                ax.axhline(baseline - threshold, color="#526980", linestyle=":", linewidth=0.9)
        ax.set_xlim(min(float(x[0]), -5.0), 0.0)
    ax.set_title(f"LIVE {selected_mode.upper()}", loc="left", color=TEXT, fontsize=10, pad=10)
    ax.set_xlabel("Seconds from now", color="#71839b", fontsize=8)
    ax.set_ylabel("CSI amplitude" if selected_mode == "CSI amplitude" else "RSSI (dBm)", color="#71839b", fontsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    ax.tick_params(colors="#71839b", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    fig.tight_layout(pad=1.5)
    return fig


def make_radar(*, moving: bool, event_count: int, elapsed: float | None = None) -> Figure:
    """Draw an illustrative room scanner; the dot carries no position data."""
    now = time.monotonic() if elapsed is None else elapsed
    angle = (now * 50.0) % 360.0
    fig = Figure(figsize=(4.4, 4.4), dpi=110, facecolor=BG)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_facecolor(BG)
    ax.set_aspect("equal")
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)
    ax.axis("off")
    for radius in (0.25, 0.5, 0.75, 1.0):
        ax.add_patch(Circle((0, 0), radius, fill=False, color=GRID, linewidth=0.8))
    for bearing in range(0, 360, 45):
        radians = math.radians(bearing)
        ax.plot([0, math.cos(radians)], [0, math.sin(radians)], color=GRID, linewidth=0.6)
    ax.add_patch(Wedge((0, 0), 1.0, angle - 18, angle, color=TEAL, alpha=0.10))
    ax.plot([0, math.cos(math.radians(angle))], [0, math.sin(math.radians(angle))], color=TEAL, linewidth=1.5, alpha=0.8)
    ax.scatter([0], [0], s=30, color=TEAL, zorder=4)
    if moving:
        # Fixed example marker intentionally avoids implying measured location.
        marker_angle = math.radians((event_count * 73 + 28) % 360)
        x, y = 0.58 * math.cos(marker_angle), 0.58 * math.sin(marker_angle)
        ax.scatter([x], [y], s=105, color=AMBER, alpha=0.2, zorder=3)
        ax.scatter([x], [y], s=28, color=AMBER, zorder=4)
    ax.text(0, -1.08, "ILLUSTRATIVE SWEEP · NO POSITION ESTIMATE", color="#71839b", fontsize=7.5, ha="center")
    fig.tight_layout(pad=0.4)
    return fig
