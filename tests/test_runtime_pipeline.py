import unittest

from tests.test_action_queue import _Controller
from tests.test_primitives import _feature


class TouchlessPipelineTests(unittest.TestCase):
    def test_dispatches_movement_only_while_pointing_or_dragging(self) -> None:
        from touchless_control.runtime import TouchlessPipeline

        pipeline = TouchlessPipeline()
        controller = _Controller()

        pipeline.step(_feature(timestamp_ms=1))
        pipeline.step(_feature(timestamp_ms=2, hand_velocity_norm=(0.05, 0.0)))
        pipeline.flush(controller)

        self.assertEqual([command.type for command in controller.commands], ["move_relative"])

    def test_paused_state_blocks_click_scroll_and_movement_dispatch(self) -> None:
        from touchless_control.runtime import TouchlessPipeline

        pipeline = TouchlessPipeline()
        controller = _Controller()

        pipeline.step(_feature(timestamp_ms=1))
        pipeline.step(_feature(timestamp_ms=2, open_palm=True, finger_count=5))
        pipeline.step(
            _feature(
                timestamp_ms=3,
                open_palm=True,
                finger_count=5,
                pinch_ratio=0.29,
                two_finger_ready=True,
                hand_velocity_norm=(0.05, -0.08),
            )
        )
        pipeline.flush(controller)

        self.assertEqual(pipeline.state, "Paused")
        self.assertEqual(controller.commands, [])

    def test_intent_context_preserves_hand_only_pipeline_behavior(self) -> None:
        from touchless_control.contracts import IntentContext
        from touchless_control.runtime import TouchlessPipeline

        pipeline = TouchlessPipeline()
        controller = _Controller()

        pipeline.step_context(IntentContext.from_hand(_feature(timestamp_ms=1)))
        pipeline.step_context(
            IntentContext.from_hand(
                _feature(timestamp_ms=2, hand_velocity_norm=(0.05, 0.0))
            )
        )
        pipeline.flush(controller)

        self.assertEqual([command.type for command in controller.commands], ["move_relative"])

    def test_attention_off_screen_blocks_movement_dispatch(self) -> None:
        from touchless_control.contracts import AttentionFrame, IntentContext
        from touchless_control.runtime import TouchlessPipeline

        pipeline = TouchlessPipeline()
        controller = _Controller()
        attention = AttentionFrame(
            timestamp_ms=2,
            face_present=True,
            attention_on_screen=False,
            gaze_vector_norm=(0.5, 0.0),
            confidence=0.9,
        )

        pipeline.step_context(IntentContext.from_hand(_feature(timestamp_ms=1)))
        pipeline.step_context(
            IntentContext(
                timestamp_ms=2,
                hand_features=_feature(timestamp_ms=2, hand_velocity_norm=(0.05, 0.0)),
                attention_frame=attention,
            )
        )
        pipeline.flush(controller)

        self.assertEqual(controller.commands, [])

    def test_attention_off_screen_safely_releases_active_drag(self) -> None:
        from touchless_control.contracts import AttentionFrame, IntentContext
        from touchless_control.runtime import TouchlessPipeline

        pipeline = TouchlessPipeline()
        controller = _Controller()
        pipeline.step(_feature(timestamp_ms=1))
        pipeline.step(_feature(timestamp_ms=20, pinch_ratio=0.29))
        pipeline.step(_feature(timestamp_ms=320, pinch_ratio=0.29))

        attention = AttentionFrame(
            timestamp_ms=330,
            face_present=True,
            attention_on_screen=False,
            gaze_vector_norm=(0.8, 0.0),
            confidence=0.95,
        )
        pipeline.step_context(
            IntentContext(
                timestamp_ms=330,
                hand_features=_feature(timestamp_ms=330, hand_velocity_norm=(0.05, 0.0)),
                attention_frame=attention,
            )
        )
        pipeline.flush(controller)

        self.assertEqual([command.type for command in controller.commands], ["left_down", "left_up"])

    def test_attention_release_cancels_drag_state_before_attention_returns(self) -> None:
        from touchless_control.contracts import AttentionFrame, IntentContext
        from touchless_control.runtime import TouchlessPipeline

        pipeline = TouchlessPipeline()
        controller = _Controller()
        pipeline.step(_feature(timestamp_ms=1))
        pipeline.step(_feature(timestamp_ms=20, pinch_ratio=0.29))
        pipeline.step(_feature(timestamp_ms=320, pinch_ratio=0.29))

        pipeline.step_context(
            IntentContext(
                timestamp_ms=330,
                hand_features=_feature(timestamp_ms=330, hand_velocity_norm=(0.05, 0.0)),
                attention_frame=AttentionFrame(
                    timestamp_ms=330,
                    face_present=True,
                    attention_on_screen=False,
                    gaze_vector_norm=(0.8, 0.0),
                    confidence=0.95,
                ),
            )
        )
        pipeline.step(_feature(timestamp_ms=340, hand_velocity_norm=(0.05, 0.0)))
        pipeline.flush(controller)

        self.assertEqual(pipeline.state, "Cooldown")
        self.assertEqual([command.type for command in controller.commands], ["left_down", "left_up"])


if __name__ == "__main__":
    unittest.main()
