from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

ACTIVE_MOVEMENT_SCENARIOS = frozenset({"move-slow-precise", "move-straight"})


@dataclass(frozen=True, slots=True)
class SessionReport:
    total_records: int
    duration_s: float
    effective_fps: float
    action_count: int
    dispatch_count: int
    failure_count: int
    tracking_loss_count: int
    p95_latency_ms: float | None
    p99_latency_ms: float | None
    primitive_counts: dict[str, int]
    action_counts: dict[str, int]
    scenario_counts: dict[str, int] = field(default_factory=dict)
    move_count: int = 0
    cursor_update_hz: float = 0.0
    movement_coverage: float = 0.0
    move_gap_p50_ms: float | None = None
    move_gap_p95_ms: float | None = None
    move_gap_max_ms: float | None = None
    stationary_jitter_rms_px: float | None = None
    max_cursor_freeze_ms: float | None = None

    def to_lines(self) -> tuple[str, ...]:
        return (
            "session_report "
            f"total_records={self.total_records} "
            f"duration_s={self.duration_s:.3f} "
            f"effective_fps={self.effective_fps:.2f} "
            f"actions={self.action_count} "
            f"dispatches={self.dispatch_count} "
            f"failures={self.failure_count} "
            f"tracking_loss={self.tracking_loss_count} "
            f"p95_latency_ms={_format_optional(self.p95_latency_ms)} "
            f"p99_latency_ms={_format_optional(self.p99_latency_ms)} "
            f"cursor_update_hz={self.cursor_update_hz:.2f} "
            f"movement_coverage={self.movement_coverage:.2f} "
            f"move_gap_p95_ms={_format_optional(self.move_gap_p95_ms)} "
            f"stationary_jitter_rms_px={_format_optional(self.stationary_jitter_rms_px)} "
            f"max_cursor_freeze_ms={_format_optional(self.max_cursor_freeze_ms)}",
            "primitives " + _format_counts(self.primitive_counts),
            "actions " + _format_counts(self.action_counts),
            "scenarios " + _format_counts(self.scenario_counts),
        )


def analyze_session_log(path: str) -> SessionReport:
    with open(path, "r", encoding="utf-8") as log_file:
        entries = [
            json.loads(line)
            for line in log_file
            if line.strip()
        ]
    return analyze_session_entries(entries)


def analyze_session_entries(entries: Iterable[dict[str, Any]]) -> SessionReport:
    records = list(entries)
    timestamps = [int(entry["timestamp_ms"]) for entry in records]
    latencies = [
        float(entry["latency_ms"])
        for entry in records
        if entry.get("latency_ms") is not None
    ]
    primitive_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()
    action_count = 0
    dispatch_count = 0
    failure_count = 0
    tracking_loss_count = 0

    for entry in records:
        scenario_label = entry.get("scenario_label")
        if scenario_label:
            scenario_counts.update((str(scenario_label),))
        primitive_counts.update(entry.get("primitive_types", ()))
        action_types = entry.get("action_types", ())
        action_counts.update(action_types)
        action_count += len(action_types)
        dispatch_successes = entry.get("dispatch_successes", ())
        dispatch_count += len(dispatch_successes)
        failure_count += sum(1 for success in dispatch_successes if not success)
        features = entry.get("features", {})
        if features.get("tracking_lost"):
            tracking_loss_count += 1

    duration_s = _duration_s(timestamps)
    effective_fps = (len(records) / duration_s) if duration_s > 0 else 0.0
    has_scenario_labels = any(entry.get("scenario_label") for entry in records)
    movement_records = (
        [
            entry
            for entry in records
            if entry.get("scenario_label") in ACTIVE_MOVEMENT_SCENARIOS
        ]
        if has_scenario_labels
        else records
    )
    movement_frame_timestamps = [
        int(entry["timestamp_ms"]) for entry in movement_records
    ]
    move_timestamps = [
        int(entry["timestamp_ms"])
        for entry in movement_records
        if "move_relative" in entry.get("action_types", ())
    ]
    movement_duration_s = _duration_s(movement_frame_timestamps)
    move_gaps = (
        _active_move_gaps(movement_frame_timestamps, move_timestamps)
        if has_scenario_labels
        else _gaps(move_timestamps)
    )
    move_count = len(move_timestamps)
    stationary_jitter = _stationary_jitter_rms(records)
    max_freeze = max(move_gaps) if move_gaps else None
    return SessionReport(
        total_records=len(records),
        duration_s=duration_s,
        effective_fps=effective_fps,
        action_count=action_count,
        dispatch_count=dispatch_count,
        failure_count=failure_count,
        tracking_loss_count=tracking_loss_count,
        p95_latency_ms=_percentile(latencies, 0.95),
        p99_latency_ms=_percentile(latencies, 0.99),
        primitive_counts=dict(sorted(primitive_counts.items())),
        action_counts=dict(sorted(action_counts.items())),
        scenario_counts=dict(sorted(scenario_counts.items())),
        move_count=move_count,
        cursor_update_hz=(
            move_count / movement_duration_s if movement_duration_s > 0 else 0.0
        ),
        movement_coverage=(
            move_count / len(movement_records) if movement_records else 0.0
        ),
        move_gap_p50_ms=_percentile(move_gaps, 0.50),
        move_gap_p95_ms=_percentile(move_gaps, 0.95),
        move_gap_max_ms=max_freeze,
        stationary_jitter_rms_px=stationary_jitter,
        max_cursor_freeze_ms=max_freeze,
    )


def _duration_s(timestamps: list[int]) -> float:
    if len(timestamps) < 2:
        return 0.0
    return (max(timestamps) - min(timestamps)) / 1000.0


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _gaps(timestamps: list[int]) -> list[float]:
    return [
        float(current - previous)
        for previous, current in zip(timestamps, timestamps[1:])
    ]


def _active_move_gaps(
    frame_timestamps: list[int],
    move_timestamps: list[int],
) -> list[float]:
    if not frame_timestamps or not move_timestamps:
        return []
    gaps = _gaps(move_timestamps)
    leading_gap = move_timestamps[0] - frame_timestamps[0]
    trailing_gap = frame_timestamps[-1] - move_timestamps[-1]
    if leading_gap > 0:
        gaps.insert(0, float(leading_gap))
    if trailing_gap > 0:
        gaps.append(float(trailing_gap))
    return gaps


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return " ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def _format_optional(value: float | None) -> str:
    if value is None:
        return "None"
    return f"{value:.1f}"


def _stationary_jitter_rms(records: Sequence[dict[str, Any]]) -> float | None:
    """Compute cursor jitter RMS for labeled stationary scenarios.

    Unlabeled legacy logs fall back to the former hand-velocity estimate.
    Labeled logs without cursor delta payloads remain unverifiable.
    """
    stationary_records = [
        entry for entry in records if entry.get("scenario_label") == "move-stationary"
    ]
    if stationary_records:
        if not any("cursor_deltas_px" in entry for entry in stationary_records):
            return None
        squared_distances = [
            float(dx) ** 2 + float(dy) ** 2
            for entry in stationary_records
            for dx, dy in entry.get("cursor_deltas_px", ())
        ]
        if not squared_distances:
            return 0.0
        return math.sqrt(sum(squared_distances) / len(squared_distances))

    jitter_deltas: list[float] = []
    for entry in records:
        action_types = entry.get("action_types", ())
        if "move_relative" not in action_types:
            continue
        features = entry.get("features", {})
        velocity = features.get("hand_velocity_norm")
        if velocity is None:
            continue
        speed = math.hypot(*velocity) if isinstance(velocity, (list, tuple)) else 0.0
        # Consider frames with very low hand velocity as 'stationary'
        if speed > 0.008:
            continue
        # These are unexpected small cursor moves during near-stillness = jitter
        jitter_deltas.append(speed)

    if not jitter_deltas:
        return None
    mean_sq = sum(v * v for v in jitter_deltas) / len(jitter_deltas)
    return math.sqrt(mean_sq) * 900  # Approximate conversion to px using base gain
