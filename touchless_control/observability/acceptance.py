from __future__ import annotations

from dataclasses import dataclass, replace

from touchless_control.core.config import SensitivityPreset
from touchless_control.observability.logger import SessionSummary


@dataclass(frozen=True, slots=True)
class AcceptanceCriteria:
    p95_latency_ms: float = 80.0
    max_false_clicks_per_minute: float = 0.5
    max_false_drags_per_100_clicks: int = 2


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    name: str
    passed: bool
    actual: float
    threshold: float


@dataclass(frozen=True, slots=True)
class AcceptanceEvaluator:
    criteria: AcceptanceCriteria = AcceptanceCriteria()

    def evaluate_summary(self, summary: SessionSummary) -> tuple[AcceptanceCheck, ...]:
        p95_latency = summary.p95_latency_ms if summary.p95_latency_ms is not None else float("inf")
        return (
            AcceptanceCheck(
                name="p95_latency_ms",
                passed=p95_latency <= self.criteria.p95_latency_ms,
                actual=p95_latency,
                threshold=self.criteria.p95_latency_ms,
            ),
            AcceptanceCheck(
                name="dispatch_failures",
                passed=summary.failure_count == 0,
                actual=float(summary.failure_count),
                threshold=0.0,
            ),
        )

    def tune_thresholds(
        self,
        preset: SensitivityPreset,
        *,
        false_clicks_per_minute: float,
        false_drags_per_100_clicks: int,
    ) -> SensitivityPreset:
        pinch_close_ratio = preset.pinch_close_ratio
        click_motion_guard = preset.click_motion_guard
        drag_hold_threshold_ms = preset.drag_hold_threshold_ms
        early_drag_motion_threshold = preset.early_drag_motion_threshold

        if false_clicks_per_minute > self.criteria.max_false_clicks_per_minute:
            pinch_close_ratio = _clamp(pinch_close_ratio - 0.03, 0.20, 0.40)
            click_motion_guard = _clamp(click_motion_guard * 0.85, 0.02, 0.09)

        if false_drags_per_100_clicks > self.criteria.max_false_drags_per_100_clicks:
            drag_hold_threshold_ms = min(drag_hold_threshold_ms + 40, 450)
            early_drag_motion_threshold = _clamp(
                early_drag_motion_threshold + 0.02,
                0.08,
                0.20,
            )

        return replace(
            preset,
            name=f"{preset.name}_acceptance_tuned",
            pinch_close_ratio=pinch_close_ratio,
            click_motion_guard=click_motion_guard,
            drag_hold_threshold_ms=drag_hold_threshold_ms,
            early_drag_motion_threshold=early_drag_motion_threshold,
        )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
