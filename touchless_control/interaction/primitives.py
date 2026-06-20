from __future__ import annotations

from dataclasses import dataclass, field

from touchless_control.core.config import SensitivityPreset
from touchless_control.core.contracts import FeatureFrame, PrimitiveEvent


@dataclass(slots=True)
class PrimitiveDetector:
    preset: SensitivityPreset = field(default_factory=SensitivityPreset.balanced)
    vertical_swipe_threshold: float = 0.04
    _pinch_closed: bool = False

    def detect(self, feature_frame: FeatureFrame) -> list[PrimitiveEvent]:
        if feature_frame.tracking_lost or not feature_frame.hand_present:
            self._pinch_closed = False
            return [
                PrimitiveEvent(
                    timestamp_ms=feature_frame.timestamp_ms,
                    type="tracking_lost",
                    confidence=1.0 - feature_frame.stability_score,
                    source_features={"stability_score": feature_frame.stability_score},
                )
            ]

        events = [
            PrimitiveEvent(
                timestamp_ms=feature_frame.timestamp_ms,
                type="pointing",
                confidence=feature_frame.stability_score,
                source_features={"index_tip_norm": feature_frame.index_tip_norm},
            )
        ]

        if feature_frame.open_palm:
            events.append(
                PrimitiveEvent(
                    timestamp_ms=feature_frame.timestamp_ms,
                    type="open_palm",
                    confidence=feature_frame.stability_score,
                    source_features={"finger_count": feature_frame.finger_count},
                )
            )

        events.extend(self._detect_pinch(feature_frame))
        scroll_event = self._detect_scroll(feature_frame)
        if scroll_event is not None:
            events.append(scroll_event)

        return events

    def _detect_pinch(self, feature_frame: FeatureFrame) -> list[PrimitiveEvent]:
        if (
            not self._pinch_closed
            and feature_frame.pinch_ratio <= self.preset.pinch_close_ratio
        ):
            self._pinch_closed = True
            return [
                PrimitiveEvent(
                    timestamp_ms=feature_frame.timestamp_ms,
                    type="pinch_closed",
                    confidence=feature_frame.stability_score,
                    source_features={"pinch_ratio": feature_frame.pinch_ratio},
                )
            ]

        if self._pinch_closed and feature_frame.pinch_ratio >= self.preset.pinch_open_ratio:
            self._pinch_closed = False
            return [
                PrimitiveEvent(
                    timestamp_ms=feature_frame.timestamp_ms,
                    type="pinch_opened",
                    confidence=feature_frame.stability_score,
                    source_features={"pinch_ratio": feature_frame.pinch_ratio},
                )
            ]

        return []

    def _detect_scroll(self, feature_frame: FeatureFrame) -> PrimitiveEvent | None:
        velocity_x, velocity_y = feature_frame.hand_velocity_norm
        if (
            self._pinch_closed
            or not feature_frame.two_finger_ready
            or abs(velocity_y) < self.vertical_swipe_threshold
            or abs(velocity_y) <= abs(velocity_x)
        ):
            return None

        return PrimitiveEvent(
            timestamp_ms=feature_frame.timestamp_ms,
            type="two_finger_swipe",
            confidence=feature_frame.stability_score,
            source_features={
                "direction": "up" if velocity_y < 0 else "down",
                "velocity": feature_frame.hand_velocity_norm,
            },
        )
