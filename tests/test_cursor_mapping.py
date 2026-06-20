import unittest
from dataclasses import replace

from tests.test_primitives import _feature


class CursorMapperTests(unittest.TestCase):
    def test_deadzone_emits_none_command_for_micro_motion(self) -> None:
        from touchless_control.control import CursorMapper

        command = CursorMapper().map_motion(
            _feature(timestamp_ms=10, hand_velocity_norm=(0.001, 0.001))
        )

        self.assertEqual(command.type, "none")

    def test_maps_hand_velocity_to_relative_cursor_delta(self) -> None:
        from touchless_control.control import CursorMapper

        command = CursorMapper().map_motion(
            _feature(timestamp_ms=20, hand_velocity_norm=(0.02, -0.01))
        )

        self.assertEqual(command.type, "move_relative")
        self.assertIsInstance(command.dx_px, int)
        self.assertIsInstance(command.dy_px, int)
        self.assertNotEqual((command.dx_px, command.dy_px), (0, 0))
        self.assertEqual(command.source_state, "Pointing")

    def test_clamps_large_motion_to_max_step(self) -> None:
        from touchless_control.control import CursorMapper

        feature = replace(_feature(timestamp_ms=30), hand_velocity_norm=(5.0, -5.0))
        command = CursorMapper().map_motion(feature)

        self.assertLessEqual(abs(command.dx_px), 120)
        self.assertLessEqual(abs(command.dy_px), 120)


if __name__ == "__main__":
    unittest.main()
