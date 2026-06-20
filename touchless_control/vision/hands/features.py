from __future__ import annotations

import math
from dataclasses import dataclass

from touchless_control.core.contracts import FeatureFrame, HandFrame, Point2D, Point3D

WRIST = 0
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_TIP = 12
RING_PIP = 14
RING_TIP = 16
PINKY_PIP = 18
PINKY_TIP = 20


@dataclass(slots=True)
class FeatureNormalizer:
    stability_threshold: float = 0.5
    _previous_palm_center: Point2D | None = None

    def to_features(self, hand_frame: HandFrame) -> FeatureFrame:
        stability_score = min(
            hand_frame.detection_confidence,
            hand_frame.presence_confidence,
            hand_frame.tracking_confidence,
        )
        tracking_lost = stability_score < self.stability_threshold
        landmarks = hand_frame.landmarks_img
        palm_scale = _distance_2d(landmarks[WRIST], landmarks[MIDDLE_MCP])
        palm_scale = max(palm_scale, 1e-6)
        palm_center = _midpoint_2d(landmarks[WRIST], landmarks[MIDDLE_MCP])
        hand_velocity = _delta(palm_center, self._previous_palm_center)
        self._previous_palm_center = palm_center

        thumb_tip = _point2d(landmarks[THUMB_TIP])
        index_tip = _point2d(landmarks[INDEX_TIP])
        middle_tip = _point2d(landmarks[MIDDLE_TIP])
        pinch_center = _midpoint_2d(landmarks[THUMB_TIP], landmarks[INDEX_TIP])
        pinch_ratio = _distance_2d(landmarks[THUMB_TIP], landmarks[INDEX_TIP]) / palm_scale
        finger_count = _finger_count(landmarks)

        return FeatureFrame(
            timestamp_ms=hand_frame.timestamp_ms,
            hand_present=not tracking_lost,
            stability_score=stability_score,
            palm_scale=palm_scale,
            palm_center_norm=palm_center,
            index_tip_norm=index_tip,
            thumb_tip_norm=thumb_tip,
            middle_tip_norm=middle_tip,
            index_direction=_unit_delta(_point2d(landmarks[INDEX_MCP]), index_tip),
            hand_velocity_norm=hand_velocity,
            pinch_ratio=pinch_ratio,
            pinch_center_norm=pinch_center,
            finger_count=finger_count,
            two_finger_ready=_finger_is_up(landmarks, INDEX_TIP, INDEX_PIP)
            and _finger_is_up(landmarks, MIDDLE_TIP, MIDDLE_PIP),
            open_palm=finger_count >= 4,
            tracking_lost=tracking_lost,
        )


def _point2d(point: Point3D) -> Point2D:
    return (point[0], point[1])


def _distance_2d(a: Point3D, b: Point3D) -> float:
    return math.dist(_point2d(a), _point2d(b))


def _midpoint_2d(a: Point3D, b: Point3D) -> Point2D:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _delta(current: Point2D, previous: Point2D | None) -> Point2D:
    if previous is None:
        return (0.0, 0.0)
    return (current[0] - previous[0], current[1] - previous[1])


def _unit_delta(start: Point2D, end: Point2D) -> Point2D:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    magnitude = math.hypot(dx, dy)
    if magnitude == 0:
        return (0.0, 0.0)
    return (dx / magnitude, dy / magnitude)


def _finger_count(landmarks: tuple[Point3D, ...]) -> int:
    fingers = [
        _finger_is_up(landmarks, INDEX_TIP, INDEX_PIP),
        _finger_is_up(landmarks, MIDDLE_TIP, MIDDLE_PIP),
        _finger_is_up(landmarks, RING_TIP, RING_PIP),
        _finger_is_up(landmarks, PINKY_TIP, PINKY_PIP),
    ]
    return sum(1 for is_up in fingers if is_up)


def _finger_is_up(landmarks: tuple[Point3D, ...], tip: int, pip: int) -> bool:
    return landmarks[tip][1] < landmarks[pip][1]
