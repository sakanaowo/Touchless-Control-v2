import unittest

from tests.test_primitives import _feature
from touchless_control.contracts import ActionCommand, OSDispatchResult
from touchless_control.observability import SessionLogger


def _result(
    *,
    timestamp_ms: int,
    command_type: str,
    success: bool = True,
) -> OSDispatchResult:
    return OSDispatchResult(
        timestamp_ms=timestamp_ms,
        command_type=command_type,
        success=success,
        backend="test",
        error_code=None if success else "BackendError",
        dispatch_latency_ms=2.0,
    )


class AcceptanceEvaluatorTests(unittest.TestCase):
    def test_accepts_summary_with_latency_and_dispatch_inside_budget(self) -> None:
        from touchless_control.acceptance import AcceptanceEvaluator

        logger = SessionLogger()
        logger.record(
            feature_frame=_feature(timestamp_ms=10),
            commands=[ActionCommand.left_click(timestamp_ms=10, source_state="ClickCommitted")],
            results=[_result(timestamp_ms=11, command_type="left_click")],
            latency_ms=42.0,
        )

        checks = AcceptanceEvaluator().evaluate_summary(logger.summary())

        self.assertTrue(all(check.passed for check in checks))

    def test_flags_high_latency_and_dispatch_failures(self) -> None:
        from touchless_control.acceptance import AcceptanceEvaluator

        logger = SessionLogger()
        logger.record(
            feature_frame=_feature(timestamp_ms=20),
            results=[_result(timestamp_ms=21, command_type="left_up", success=False)],
            latency_ms=95.0,
        )

        failed_names = {
            check.name for check in AcceptanceEvaluator().evaluate_summary(logger.summary())
            if not check.passed
        }

        self.assertEqual(failed_names, {"p95_latency_ms", "dispatch_failures"})

    def test_recommends_safer_thresholds_when_false_actions_exceed_budget(self) -> None:
        from touchless_control.acceptance import AcceptanceEvaluator
        from touchless_control.config import SensitivityPreset

        preset = SensitivityPreset.balanced()
        tuned = AcceptanceEvaluator().tune_thresholds(
            preset,
            false_clicks_per_minute=0.7,
            false_drags_per_100_clicks=3,
        )

        self.assertLess(tuned.pinch_close_ratio, preset.pinch_close_ratio)
        self.assertLess(tuned.click_motion_guard, preset.click_motion_guard)
        self.assertGreater(tuned.drag_hold_threshold_ms, preset.drag_hold_threshold_ms)
        self.assertGreater(tuned.early_drag_motion_threshold, preset.early_drag_motion_threshold)


class ProductAcceptanceGateTests(unittest.TestCase):
    def test_accepts_report_meeting_all_product_thresholds(self) -> None:
        from touchless_control.acceptance import AcceptanceEvaluator
        from touchless_control.observability.report import SessionReport

        report = SessionReport(
            total_records=300,
            duration_s=10.0,
            effective_fps=35.0,
            action_count=200,
            dispatch_count=200,
            failure_count=0,
            tracking_loss_count=0,
            p95_latency_ms=40.0,
            p99_latency_ms=55.0,
            primitive_counts={},
            action_counts={"move_relative": 200},
            move_count=250,
            cursor_update_hz=25.0,
            movement_coverage=0.85,
            move_gap_p50_ms=25.0,
            move_gap_p95_ms=40.0,
            move_gap_max_ms=80.0,
            stationary_jitter_rms_px=3.0,
            max_cursor_freeze_ms=80.0,
        )

        checks = AcceptanceEvaluator().evaluate_product_report(report)

        self.assertTrue(all(check.passed for check in checks))

    def test_flags_report_with_bad_gap_coverage_fps_jitter_freeze(self) -> None:
        from touchless_control.acceptance import AcceptanceEvaluator
        from touchless_control.observability.report import SessionReport

        report = SessionReport(
            total_records=100,
            duration_s=10.0,
            effective_fps=15.0,
            action_count=30,
            dispatch_count=30,
            failure_count=0,
            tracking_loss_count=5,
            p95_latency_ms=60.0,
            p99_latency_ms=90.0,
            primitive_counts={},
            action_counts={"move_relative": 30},
            move_count=30,
            cursor_update_hz=3.0,
            movement_coverage=0.30,
            move_gap_p50_ms=100.0,
            move_gap_p95_ms=500.0,
            move_gap_max_ms=800.0,
            stationary_jitter_rms_px=12.0,
            max_cursor_freeze_ms=800.0,
        )

        checks = AcceptanceEvaluator().evaluate_product_report(report)
        failed_names = {check.name for check in checks if not check.passed}

        self.assertEqual(
            failed_names,
            {
                "cursor_update_p95_gap_ms",
                "movement_coverage",
                "effective_tracking_fps",
                "stationary_jitter_rms_px",
                "max_cursor_freeze_ms",
            },
        )

    def test_handles_report_with_missing_optional_fields(self) -> None:
        from touchless_control.acceptance import AcceptanceEvaluator
        from touchless_control.observability.report import SessionReport

        report = SessionReport(
            total_records=50,
            duration_s=5.0,
            effective_fps=10.0,
            action_count=10,
            dispatch_count=10,
            failure_count=0,
            tracking_loss_count=0,
            p95_latency_ms=30.0,
            p99_latency_ms=40.0,
            primitive_counts={},
            action_counts={},
        )

        checks = AcceptanceEvaluator().evaluate_product_report(report)

        # Missing fields should default to inf/0 and fail
        self.assertGreater(len(checks), 0)


if __name__ == "__main__":
    unittest.main()
