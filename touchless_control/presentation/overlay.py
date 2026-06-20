from __future__ import annotations

from dataclasses import dataclass

from touchless_control.core.contracts import FeatureFrame


@dataclass(frozen=True, slots=True)
class OverlaySnapshot:
    timestamp_ms: int
    state: str
    active_mode: str
    tracking_status: str
    latency_ms: float | None
    high_latency: bool
    message: str
    stability_score: float
    pinch_ratio: float


@dataclass(frozen=True, slots=True)
class OverlayPresenter:
    latency_warning_ms: float = 80.0

    def snapshot(
        self,
        *,
        feature_frame: FeatureFrame,
        state: str,
        latency_ms: float | None,
    ) -> OverlaySnapshot:
        high_latency = latency_ms is not None and latency_ms > self.latency_warning_ms
        return OverlaySnapshot(
            timestamp_ms=feature_frame.timestamp_ms,
            state=state,
            active_mode=_active_mode_for(state),
            tracking_status=_tracking_status_for(feature_frame),
            latency_ms=latency_ms,
            high_latency=high_latency,
            message="latency_warning" if high_latency else "ok",
            stability_score=feature_frame.stability_score,
            pinch_ratio=feature_frame.pinch_ratio,
        )


def _active_mode_for(state: str) -> str:
    return {
        "ClickCandidate": "click_candidate",
        "ClickCommitted": "click",
        "Dragging": "drag",
        "Scrolling": "scroll",
        "Paused": "paused",
        "TrackingLost": "tracking_lost",
        "NoHand": "no_hand",
    }.get(state, "pointing")


def _tracking_status_for(feature_frame: FeatureFrame) -> str:
    if feature_frame.tracking_lost:
        return "tracking_lost"
    if feature_frame.hand_present:
        return "stable"
    return "no_hand"
