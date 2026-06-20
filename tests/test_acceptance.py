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


if __name__ == "__main__":
    unittest.main()
