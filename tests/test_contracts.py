import dataclasses
import unittest


class ContractLayoutTests(unittest.TestCase):
    def test_public_contracts_are_importable(self) -> None:
        from touchless_control.contracts import (
            ActionCommand,
            AttentionFrame,
            FaceFrame,
            FeatureFrame,
            HandFrame,
            IntentContext,
            IntentSignal,
            InteractionEvent,
            OSDispatchResult,
            PrimitiveEvent,
        )

        for contract in (
            ActionCommand,
            AttentionFrame,
            FaceFrame,
            FeatureFrame,
            HandFrame,
            IntentContext,
            IntentSignal,
            InteractionEvent,
            OSDispatchResult,
            PrimitiveEvent,
        ):
            self.assertTrue(dataclasses.is_dataclass(contract))

    def test_action_command_is_immutable_and_relative(self) -> None:
        from touchless_control.contracts import ActionCommand

        command = ActionCommand.move_relative(
            timestamp_ms=100,
            dx_px=12,
            dy_px=-8,
            source_state="Pointing",
        )

        self.assertEqual(command.type, "move_relative")
        self.assertEqual(command.dx_px, 12)
        self.assertEqual(command.dy_px, -8)
        self.assertIsNone(command.wheel_delta)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            command.dx_px = 99

    def test_default_sensitivity_matches_requirements_baseline(self) -> None:
        from touchless_control.config import SensitivityPreset

        preset = SensitivityPreset.balanced()

        self.assertEqual(preset.name, "balanced")
        self.assertEqual(preset.drag_hold_threshold_ms, 280)
        self.assertEqual(preset.max_step_px, 120)
        self.assertAlmostEqual(preset.deadzone, 0.015)
        self.assertAlmostEqual(preset.pinch_close_ratio, 0.30)
        self.assertAlmostEqual(preset.pinch_open_ratio, 0.45)

    def test_intent_context_supports_optional_face_and_attention_inputs(self) -> None:
        from touchless_control.contracts import AttentionFrame, FaceFrame, IntentContext, IntentSignal

        face = FaceFrame(
            timestamp_ms=10,
            face_present=True,
            bounding_box_norm=(0.1, 0.2, 0.3, 0.4),
            identity_id=None,
            detection_confidence=0.9,
            tracking_confidence=0.8,
        )
        attention = AttentionFrame(
            timestamp_ms=10,
            face_present=True,
            attention_on_screen=True,
            gaze_vector_norm=(0.0, -0.1),
            confidence=0.85,
        )
        signal = IntentSignal(
            timestamp_ms=10,
            type="attention_confirmed",
            confidence=0.85,
            reason="face_attention_on_screen",
            source_features={"face_present": True},
        )
        context = IntentContext(
            timestamp_ms=10,
            hand_features=None,
            face_frame=face,
            attention_frame=attention,
            intent_signals=(signal,),
        )

        self.assertIs(context.face_frame, face)
        self.assertIs(context.attention_frame, attention)
        self.assertEqual(context.intent_signals[0].source_features["face_present"], True)

        with self.assertRaises(TypeError):
            context.intent_signals[0].source_features["face_present"] = False


if __name__ == "__main__":
    unittest.main()
