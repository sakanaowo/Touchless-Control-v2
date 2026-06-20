from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

Point2D = tuple[float, float]
Point3D = tuple[float, float, float]
Box2D = tuple[float, float, float, float]


def _readonly_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True, slots=True)
class HandFrame:
    timestamp_ms: int
    image_width: int
    image_height: int
    landmarks_img: tuple[Point3D, ...]
    landmarks_world: tuple[Point3D, ...]
    handedness: str
    detection_confidence: float
    presence_confidence: float
    tracking_confidence: float


@dataclass(frozen=True, slots=True)
class FeatureFrame:
    timestamp_ms: int
    hand_present: bool
    stability_score: float
    palm_scale: float
    palm_center_norm: Point2D
    index_tip_norm: Point2D
    thumb_tip_norm: Point2D
    middle_tip_norm: Point2D
    index_direction: Point2D
    hand_velocity_norm: Point2D
    pinch_ratio: float
    pinch_center_norm: Point2D
    finger_count: int
    two_finger_ready: bool
    open_palm: bool
    tracking_lost: bool


@dataclass(frozen=True, slots=True)
class FaceFrame:
    timestamp_ms: int
    face_present: bool
    bounding_box_norm: Box2D
    identity_id: str | None
    detection_confidence: float
    tracking_confidence: float


@dataclass(frozen=True, slots=True)
class AttentionFrame:
    timestamp_ms: int
    face_present: bool
    attention_on_screen: bool
    gaze_vector_norm: Point2D
    confidence: float


@dataclass(frozen=True, slots=True)
class IntentSignal:
    timestamp_ms: int
    type: str
    confidence: float
    reason: str
    source_features: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_features", _readonly_mapping(self.source_features))


@dataclass(frozen=True, slots=True)
class IntentContext:
    timestamp_ms: int
    hand_features: FeatureFrame | None = None
    face_frame: FaceFrame | None = None
    attention_frame: AttentionFrame | None = None
    intent_signals: tuple[IntentSignal, ...] = ()

    @classmethod
    def from_hand(cls, hand_features: FeatureFrame) -> IntentContext:
        return cls(
            timestamp_ms=hand_features.timestamp_ms,
            hand_features=hand_features,
        )


@dataclass(frozen=True, slots=True)
class PrimitiveEvent:
    timestamp_ms: int
    type: str
    confidence: float
    source_features: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_features", _readonly_mapping(self.source_features))


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    timestamp_ms: int
    prev_state: str
    new_state: str
    reason: str
    confidence: float
    elapsed_in_prev_state_ms: int


@dataclass(frozen=True, slots=True)
class ActionCommand:
    timestamp_ms: int
    type: str
    source_state: str
    dx_px: int | None = None
    dy_px: int | None = None
    wheel_delta: int | None = None

    @classmethod
    def move_relative(
        cls,
        *,
        timestamp_ms: int,
        dx_px: int,
        dy_px: int,
        source_state: str,
    ) -> ActionCommand:
        return cls(
            timestamp_ms=timestamp_ms,
            type="move_relative",
            source_state=source_state,
            dx_px=dx_px,
            dy_px=dy_px,
        )

    @classmethod
    def left_click(cls, *, timestamp_ms: int, source_state: str) -> ActionCommand:
        return cls(timestamp_ms=timestamp_ms, type="left_click", source_state=source_state)

    @classmethod
    def left_down(cls, *, timestamp_ms: int, source_state: str) -> ActionCommand:
        return cls(timestamp_ms=timestamp_ms, type="left_down", source_state=source_state)

    @classmethod
    def left_up(cls, *, timestamp_ms: int, source_state: str) -> ActionCommand:
        return cls(timestamp_ms=timestamp_ms, type="left_up", source_state=source_state)

    @classmethod
    def scroll_vertical(
        cls,
        *,
        timestamp_ms: int,
        wheel_delta: int,
        source_state: str,
    ) -> ActionCommand:
        return cls(
            timestamp_ms=timestamp_ms,
            type="scroll_vertical",
            source_state=source_state,
            wheel_delta=wheel_delta,
        )

    @classmethod
    def none(cls, *, timestamp_ms: int, source_state: str) -> ActionCommand:
        return cls(timestamp_ms=timestamp_ms, type="none", source_state=source_state)


@dataclass(frozen=True, slots=True)
class OSDispatchResult:
    timestamp_ms: int
    command_type: str
    success: bool
    backend: str
    error_code: str | None
    dispatch_latency_ms: float
