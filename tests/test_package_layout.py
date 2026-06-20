import unittest


class PackageLayoutTests(unittest.TestCase):
    def test_new_scaled_package_paths_are_importable(self) -> None:
        from touchless_control.control.cursor import CursorMapper
        from touchless_control.control.os.factory import create_mouse_controller
        from touchless_control.control.queue import ActionQueue
        from touchless_control.core.contracts import IntentContext
        from touchless_control.interaction.primitives import PrimitiveDetector
        from touchless_control.interaction.state_machine import InteractionStateMachine
        from touchless_control.runtime.pipeline import TouchlessPipeline
        from touchless_control.vision.camera import CameraSmokeRunner
        from touchless_control.vision.hands.features import FeatureNormalizer
        from touchless_control.vision.hands.mediapipe import MediaPipeHandPerception

        self.assertIsNotNone(ActionQueue)
        self.assertIsNotNone(CameraSmokeRunner)
        self.assertIsNotNone(CursorMapper)
        self.assertIsNotNone(FeatureNormalizer)
        self.assertIsNotNone(IntentContext)
        self.assertIsNotNone(InteractionStateMachine)
        self.assertIsNotNone(MediaPipeHandPerception)
        self.assertIsNotNone(PrimitiveDetector)
        self.assertIsNotNone(TouchlessPipeline)
        self.assertIsNotNone(create_mouse_controller)

    def test_legacy_package_paths_still_export_public_api(self) -> None:
        from touchless_control.control import ActionQueue
        from touchless_control.contracts import IntentContext
        from touchless_control.interaction import InteractionStateMachine
        from touchless_control.runtime import TouchlessPipeline

        self.assertIsNotNone(ActionQueue)
        self.assertIsNotNone(IntentContext)
        self.assertIsNotNone(InteractionStateMachine)
        self.assertIsNotNone(TouchlessPipeline)


if __name__ == "__main__":
    unittest.main()
