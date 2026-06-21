from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


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
    move_count: int = 0
    cursor_update_hz: float = 0.0
    movement_coverage: float = 0.0
    move_gap_p50_ms: float | None = None
    move_gap_p95_ms: float | None = None
    move_gap_max_ms: float | None = None

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
            f"move_gap_p95_ms={_format_optional(self.move_gap_p95_ms)}",
            "primitives " + _format_counts(self.primitive_counts),
            "actions " + _format_counts(self.action_counts),
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
    action_count = 0
    dispatch_count = 0
    failure_count = 0
    tracking_loss_count = 0
    move_timestamps: list[int] = []

    for entry in records:
        primitive_counts.update(entry.get("primitive_types", ()))
        action_types = entry.get("action_types", ())
        action_counts.update(action_types)
        if "move_relative" in action_types:
            move_timestamps.append(int(entry["timestamp_ms"]))
        action_count += len(action_types)
        dispatch_successes = entry.get("dispatch_successes", ())
        dispatch_count += len(dispatch_successes)
        failure_count += sum(1 for success in dispatch_successes if not success)
        features = entry.get("features", {})
        if features.get("tracking_lost"):
            tracking_loss_count += 1

    duration_s = _duration_s(timestamps)
    effective_fps = (len(records) / duration_s) if duration_s > 0 else 0.0
    move_gaps = _gaps(move_timestamps)
    move_count = len(move_timestamps)
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
        move_count=move_count,
        cursor_update_hz=(move_count / duration_s) if duration_s > 0 else 0.0,
        movement_coverage=(move_count / len(records)) if records else 0.0,
        move_gap_p50_ms=_percentile(move_gaps, 0.50),
        move_gap_p95_ms=_percentile(move_gaps, 0.95),
        move_gap_max_ms=max(move_gaps) if move_gaps else None,
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


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return " ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def _format_optional(value: float | None) -> str:
    if value is None:
        return "None"
    return f"{value:.1f}"
