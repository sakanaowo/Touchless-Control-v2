import unittest

from tests.test_primitives import _feature
from touchless_control.contracts import (
    ActionCommand,
    InteractionEvent,
    OSDispatchResult,
    PrimitiveEvent,
)


class SessionLoggerTests(unittest.TestCase):
    def test_records_product_acceptance_scenario_label(self) -> None:
        from touchless_control.observability import SessionLogger

        logger = SessionLogger()
        entry = logger.record(
            feature_frame=_feature(timestamp_ms=100),
            scenario_label="move-slow-precise",
        )

        self.assertEqual(entry.scenario_label, "move-slow-precise")

    def test_records_dispatched_cursor_deltas_for_jitter_analysis(self) -> None:
        from touchless_control.observability import SessionLogger

        logger = SessionLogger()
        entry = logger.record(
            feature_frame=_feature(timestamp_ms=110),
            commands=[
                ActionCommand.move_relative(
                    timestamp_ms=110,
                    dx_px=3,
                    dy_px=-2,
                    source_state="Pointing",
                ),
                ActionCommand.left_click(
                    timestamp_ms=110,
                    source_state="ClickCommitted",
                ),
            ],
            scenario_label="move-stationary",
        )

        self.assertEqual(entry.cursor_deltas_px, ((3, -2),))

    def test_records_structured_feature_state_action_and_outcome_data(self) -> None:
        from touchless_control.observability import SessionLogger

        logger = SessionLogger()
        logger.record(
            feature_frame=_feature(timestamp_ms=200, pinch_ratio=0.28),
            primitive_events=[
                PrimitiveEvent(
                    timestamp_ms=200,
                    type="pinch_closed",
                    confidence=0.95,
                    source_features={"pinch_ratio": 0.28},
                )
            ],
            interaction_events=[
                InteractionEvent(
                    timestamp_ms=200,
                    prev_state="Pointing",
                    new_state="ClickCandidate",
                    reason="pinch_closed",
                    confidence=0.95,
                    elapsed_in_prev_state_ms=120,
                )
            ],
            commands=[
                ActionCommand.left_down(timestamp_ms=200, source_state="Dragging"),
            ],
            results=[
                OSDispatchResult(
                    timestamp_ms=201,
                    command_type="left_down",
                    success=True,
                    backend="windows_sendinput",
                    error_code=None,
                    dispatch_latency_ms=3.5,
                )
            ],
            latency_ms=18.0,
        )

        entry = logger.entries[0]
        self.assertEqual(entry.timestamp_ms, 200)
        self.assertEqual(entry.state, "ClickCandidate")
        self.assertEqual(entry.primitive_types, ("pinch_closed",))
        self.assertEqual(entry.action_types, ("left_down",))
        self.assertEqual(entry.dispatch_successes, (True,))
        self.assertEqual(entry.latency_ms, 18.0)
        self.assertEqual(entry.features["pinch_ratio"], 0.28)

    def test_summarizes_latency_dispatch_failures_and_tracking_loss(self) -> None:
        from touchless_control.observability import SessionLogger

        logger = SessionLogger()
        logger.record(
            feature_frame=_feature(timestamp_ms=1),
            commands=[ActionCommand.left_click(timestamp_ms=1, source_state="ClickCommitted")],
            results=[
                OSDispatchResult(
                    timestamp_ms=2,
                    command_type="left_click",
                    success=True,
                    backend="linux_uinput",
                    error_code=None,
                    dispatch_latency_ms=4.0,
                )
            ],
            latency_ms=20.0,
        )
        logger.record(
            feature_frame=_feature(timestamp_ms=3, hand_present=False, tracking_lost=True),
            results=[
                OSDispatchResult(
                    timestamp_ms=4,
                    command_type="left_up",
                    success=False,
                    backend="linux_uinput",
                    error_code="PermissionError",
                    dispatch_latency_ms=9.0,
                )
            ],
            latency_ms=90.0,
        )

        summary = logger.summary()

        self.assertEqual(summary.total_records, 2)
        self.assertEqual(summary.action_count, 1)
        self.assertEqual(summary.dispatch_count, 2)
        self.assertEqual(summary.failure_count, 1)
        self.assertEqual(summary.tracking_loss_count, 1)
        self.assertEqual(summary.p95_latency_ms, 90.0)


if __name__ == "__main__":
    unittest.main()
