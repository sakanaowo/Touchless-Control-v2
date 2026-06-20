from __future__ import annotations

import math
from dataclasses import dataclass, field

from touchless_control.core.config import SensitivityPreset
from touchless_control.core.contracts import (
    ActionCommand,
    FeatureFrame,
    InteractionEvent,
    Point2D,
    PrimitiveEvent,
)


@dataclass(slots=True)
class InteractionStateMachine:
    preset: SensitivityPreset = field(default_factory=SensitivityPreset.balanced)
    state: str = "NoHand"
    cooldown_ms: int = 120
    _state_entered_ms: int = 0
    _candidate_started_ms: int | None = None
    _candidate_center: Point2D | None = None
    _last_scroll_dispatched_ms: int | None = None

    def step(
        self,
        feature_frame: FeatureFrame,
        primitive_events: list[PrimitiveEvent],
    ) -> list[InteractionEvent | ActionCommand]:
        events = {event.type: event for event in primitive_events}

        if "tracking_lost" in events or feature_frame.tracking_lost:
            return self._handle_tracking_lost(feature_frame)

        if self.state == "NoHand":
            if "pointing" in events:
                return [self._transition("Pointing", "hand_detected", feature_frame)]
            return []

        if self.state == "TrackingLost":
            if "pointing" in events:
                return [self._transition("Pointing", "stability_ok", feature_frame)]
            return []

        if self.state == "Paused":
            if "pointing" in events and "open_palm" not in events:
                return [self._transition("Pointing", "pointing_stable", feature_frame)]
            return []

        if self.state == "Cooldown":
            if (
                "pointing" in events
                and feature_frame.timestamp_ms - self._state_entered_ms >= self.cooldown_ms
            ):
                return [self._transition("Pointing", "cooldown_done", feature_frame)]
            return []

        if self.state == "Pointing":
            return self._step_pointing(feature_frame, events)

        if self.state == "ClickCandidate":
            return self._step_click_candidate(feature_frame, events)

        if self.state == "Dragging":
            if "pinch_opened" in events:
                return [
                    ActionCommand.left_up(
                        timestamp_ms=feature_frame.timestamp_ms,
                        source_state="Dragging",
                    ),
                    self._transition("Cooldown", "drag_released", feature_frame),
                ]
            return []

        if self.state == "Scrolling":
            return self._step_scrolling(feature_frame, events)

        return []

    def _step_pointing(
        self,
        feature_frame: FeatureFrame,
        events: dict[str, PrimitiveEvent],
    ) -> list[InteractionEvent | ActionCommand]:
        if "open_palm" in events:
            return [self._transition("Paused", "open_palm", feature_frame)]

        if "pinch_closed" in events:
            self._candidate_started_ms = feature_frame.timestamp_ms
            self._candidate_center = feature_frame.pinch_center_norm
            return [self._transition("ClickCandidate", "pinch_closed", feature_frame)]

        if "two_finger_swipe" in events:
            direction = events["two_finger_swipe"].source_features.get("direction", "up")
            wheel_delta = 120 if direction == "up" else -120
            self._last_scroll_dispatched_ms = feature_frame.timestamp_ms
            return [
                self._transition("Scrolling", "two_finger_vertical_swipe", feature_frame),
                ActionCommand.scroll_vertical(
                    timestamp_ms=feature_frame.timestamp_ms,
                    wheel_delta=wheel_delta,
                    source_state="Scrolling",
                ),
            ]

        return []

    def _step_click_candidate(
        self,
        feature_frame: FeatureFrame,
        events: dict[str, PrimitiveEvent],
    ) -> list[InteractionEvent | ActionCommand]:
        duration_ms = feature_frame.timestamp_ms - (self._candidate_started_ms or 0)
        motion = _motion_from(self._candidate_center, feature_frame.pinch_center_norm)

        if "pinch_opened" in events:
            if (
                duration_ms < self.preset.drag_hold_threshold_ms
                and motion < self.preset.click_motion_guard
            ):
                return [
                    self._transition("ClickCommitted", "short_pinch_released", feature_frame),
                    ActionCommand.left_click(
                        timestamp_ms=feature_frame.timestamp_ms,
                        source_state="ClickCommitted",
                    ),
                    self._transition("Cooldown", "click_dispatched", feature_frame),
                ]
            return [self._transition("Pointing", "pinch_release_cancelled", feature_frame)]

        if (
            duration_ms >= self.preset.drag_hold_threshold_ms
            or motion >= self.preset.early_drag_motion_threshold
        ):
            return [
                self._transition("Dragging", "drag_threshold_met", feature_frame),
                ActionCommand.left_down(
                    timestamp_ms=feature_frame.timestamp_ms,
                    source_state="Dragging",
                ),
            ]

        return []

    def _step_scrolling(
        self,
        feature_frame: FeatureFrame,
        events: dict[str, PrimitiveEvent],
    ) -> list[InteractionEvent | ActionCommand]:
        if "open_palm" in events:
            return [self._transition("Paused", "open_palm", feature_frame)]

        if "pinch_closed" in events:
            return [self._transition("Pointing", "pinch_conflict", feature_frame)]

        if "two_finger_swipe" in events:
            if not self._scroll_interval_elapsed(feature_frame.timestamp_ms):
                return []
            direction = events["two_finger_swipe"].source_features.get("direction", "up")
            self._last_scroll_dispatched_ms = feature_frame.timestamp_ms
            return [
                ActionCommand.scroll_vertical(
                    timestamp_ms=feature_frame.timestamp_ms,
                    wheel_delta=120 if direction == "up" else -120,
                    source_state="Scrolling",
                )
            ]

        if not feature_frame.two_finger_ready:
            return [self._transition("Pointing", "fingers_released", feature_frame)]

        return []

    def _handle_tracking_lost(
        self,
        feature_frame: FeatureFrame,
    ) -> list[InteractionEvent | ActionCommand]:
        outputs: list[InteractionEvent | ActionCommand] = []
        if self.state == "Dragging":
            outputs.append(
                ActionCommand.left_up(
                    timestamp_ms=feature_frame.timestamp_ms,
                    source_state="Dragging",
                )
            )
        outputs.append(self._transition("TrackingLost", "tracking_unstable", feature_frame))
        self._candidate_started_ms = None
        self._candidate_center = None
        self._last_scroll_dispatched_ms = None
        return outputs

    def _transition(
        self,
        new_state: str,
        reason: str,
        feature_frame: FeatureFrame,
    ) -> InteractionEvent:
        previous = self.state
        elapsed_ms = feature_frame.timestamp_ms - self._state_entered_ms
        self.state = new_state
        self._state_entered_ms = feature_frame.timestamp_ms
        return InteractionEvent(
            timestamp_ms=feature_frame.timestamp_ms,
            prev_state=previous,
            new_state=new_state,
            reason=reason,
            confidence=feature_frame.stability_score,
            elapsed_in_prev_state_ms=elapsed_ms,
        )

    def _scroll_interval_elapsed(self, timestamp_ms: int) -> bool:
        if self._last_scroll_dispatched_ms is None:
            return True
        return timestamp_ms - self._last_scroll_dispatched_ms >= self.preset.scroll_interval_ms


def _motion_from(start: Point2D | None, end: Point2D) -> float:
    if start is None:
        return 0.0
    return math.dist(start, end)
