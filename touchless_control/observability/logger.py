from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from touchless_control.core.contracts import (
    ActionCommand,
    FeatureFrame,
    InteractionEvent,
    OSDispatchResult,
    PrimitiveEvent,
)

PRODUCT_ACCEPTANCE_SCENARIOS = (
    "move-slow-precise",
    "move-stationary",
    "move-straight",
    "click-stability",
    "drag-stability",
    "long-session",
)


@dataclass(frozen=True, slots=True)
class SessionLogEntry:
    timestamp_ms: int
    state: str
    primitive_types: tuple[str, ...]
    interaction_reasons: tuple[str, ...]
    action_types: tuple[str, ...]
    dispatch_successes: tuple[bool, ...]
    dispatch_error_codes: tuple[str | None, ...]
    latency_ms: float | None
    features: dict[str, Any]
    scenario_label: str | None = None
    cursor_deltas_px: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class SessionSummary:
    total_records: int
    action_count: int
    dispatch_count: int
    failure_count: int
    tracking_loss_count: int
    average_latency_ms: float | None
    p95_latency_ms: float | None


@dataclass(slots=True)
class SessionLogger:
    _entries: list[SessionLogEntry] = field(default_factory=list)

    @property
    def entries(self) -> tuple[SessionLogEntry, ...]:
        return tuple(self._entries)

    def record(
        self,
        *,
        feature_frame: FeatureFrame,
        primitive_events: Sequence[PrimitiveEvent] = (),
        interaction_events: Sequence[InteractionEvent] = (),
        commands: Sequence[ActionCommand] = (),
        results: Sequence[OSDispatchResult] = (),
        latency_ms: float | None = None,
        scenario_label: str | None = None,
    ) -> SessionLogEntry:
        entry = SessionLogEntry(
            timestamp_ms=feature_frame.timestamp_ms,
            state=_state_for(feature_frame, interaction_events, commands),
            primitive_types=tuple(event.type for event in primitive_events),
            interaction_reasons=tuple(event.reason for event in interaction_events),
            action_types=tuple(command.type for command in commands),
            dispatch_successes=tuple(result.success for result in results),
            dispatch_error_codes=tuple(result.error_code for result in results),
            latency_ms=latency_ms,
            features=_feature_payload(feature_frame),
            scenario_label=scenario_label,
            cursor_deltas_px=tuple(
                (command.dx_px, command.dy_px)
                for command in commands
                if command.type == "move_relative"
                and command.dx_px is not None
                and command.dy_px is not None
            ),
        )
        self._entries.append(entry)
        return entry

    def summary(self) -> SessionSummary:
        latencies = [entry.latency_ms for entry in self._entries if entry.latency_ms is not None]
        return SessionSummary(
            total_records=len(self._entries),
            action_count=sum(len(entry.action_types) for entry in self._entries),
            dispatch_count=sum(len(entry.dispatch_successes) for entry in self._entries),
            failure_count=sum(
                1
                for entry in self._entries
                for success in entry.dispatch_successes
                if not success
            ),
            tracking_loss_count=sum(
                1 for entry in self._entries if entry.features["tracking_lost"]
            ),
            average_latency_ms=_average(latencies),
            p95_latency_ms=_percentile(latencies, 0.95),
        )


def _state_for(
    feature_frame: FeatureFrame,
    interaction_events: Sequence[InteractionEvent],
    commands: Sequence[ActionCommand],
) -> str:
    if interaction_events:
        return interaction_events[-1].new_state
    if commands:
        return commands[-1].source_state
    if feature_frame.tracking_lost:
        return "TrackingLost"
    if feature_frame.hand_present:
        return "Pointing"
    return "NoHand"


def _feature_payload(feature_frame: FeatureFrame) -> dict[str, Any]:
    return {
        "hand_present": feature_frame.hand_present,
        "stability_score": feature_frame.stability_score,
        "palm_center_norm": feature_frame.palm_center_norm,
        "hand_velocity_norm": feature_frame.hand_velocity_norm,
        "pinch_ratio": feature_frame.pinch_ratio,
        "finger_count": feature_frame.finger_count,
        "two_finger_ready": feature_frame.two_finger_ready,
        "open_palm": feature_frame.open_palm,
        "tracking_lost": feature_frame.tracking_lost,
    }


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]
