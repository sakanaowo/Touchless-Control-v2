from __future__ import annotations

from dataclasses import dataclass, replace

from touchless_control.core.config import SensitivityPreset
from touchless_control.observability.logger import SessionSummary


@dataclass(frozen=True, slots=True)
class AcceptanceCriteria:
    p95_latency_ms: float = 80.0
    max_false_clicks_per_minute: float = 0.5
    max_false_drags_per_100_clicks: int = 2
    # Product-grade pointer control thresholds
    cursor_update_p95_gap_ms: float = 50.0
    movement_coverage_min: float = 0.80
    effective_tracking_fps_min: float = 30.0
    stationary_jitter_rms_px_max: float = 6.0
    max_cursor_freeze_ms: float = 150.0


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

    def evaluate_product_report(
        self,
        report: object,
    ) -> tuple[AcceptanceCheck, ...]:
        """Evaluate a SessionReport against product-grade acceptance criteria.

        Accepts any object with the expected attributes so the import
        dependency on ``SessionReport`` remains optional at the module level.
        """
        move_gap_p95 = getattr(report, "move_gap_p95_ms", None)
        if move_gap_p95 is None:
            move_gap_p95 = float("inf")
        movement_coverage = getattr(report, "movement_coverage", 0.0)
        effective_fps = getattr(report, "effective_fps", 0.0)
        jitter_rms = getattr(report, "stationary_jitter_rms_px", None)
        if jitter_rms is None:
            jitter_rms = float("inf")
        max_freeze = getattr(report, "max_cursor_freeze_ms", None)
        if max_freeze is None:
            max_freeze = float("inf")

        return (
            AcceptanceCheck(
                name="cursor_update_p95_gap_ms",
                passed=move_gap_p95 <= self.criteria.cursor_update_p95_gap_ms,
                actual=float(move_gap_p95),
                threshold=self.criteria.cursor_update_p95_gap_ms,
            ),
            AcceptanceCheck(
                name="movement_coverage",
                passed=movement_coverage >= self.criteria.movement_coverage_min,
                actual=float(movement_coverage),
                threshold=self.criteria.movement_coverage_min,
            ),
            AcceptanceCheck(
                name="effective_tracking_fps",
                passed=effective_fps >= self.criteria.effective_tracking_fps_min,
                actual=float(effective_fps),
                threshold=self.criteria.effective_tracking_fps_min,
            ),
            AcceptanceCheck(
                name="stationary_jitter_rms_px",
                passed=jitter_rms <= self.criteria.stationary_jitter_rms_px_max,
                actual=float(jitter_rms),
                threshold=self.criteria.stationary_jitter_rms_px_max,
            ),
            AcceptanceCheck(
                name="max_cursor_freeze_ms",
                passed=max_freeze <= self.criteria.max_cursor_freeze_ms,
                actual=float(max_freeze),
                threshold=self.criteria.max_cursor_freeze_ms,
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
