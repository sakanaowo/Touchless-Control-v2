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

    def test_can_invert_configured_motion_axes(self) -> None:
        from touchless_control.control import CursorMapper

        feature = _feature(timestamp_ms=40, hand_velocity_norm=(0.03, -0.02))
        normal = CursorMapper().map_motion(feature)
        inverted = CursorMapper(invert_x=True, invert_y=True).map_motion(feature)

        self.assertEqual(inverted.dx_px, -normal.dx_px)
        self.assertEqual(inverted.dy_px, -normal.dy_px)

    def test_gain_scale_increases_cursor_response(self) -> None:
        from touchless_control.control import CursorMapper

        feature = _feature(timestamp_ms=50, hand_velocity_norm=(0.02, 0.0))
        normal = CursorMapper().map_motion(feature)
        faster = CursorMapper(gain_scale=1.5).map_motion(feature)

        self.assertGreater(abs(faster.dx_px), abs(normal.dx_px))

    def test_accumulates_small_intentional_motion_instead_of_dropping_it(self) -> None:
        from touchless_control.control import CursorMapper

        mapper = CursorMapper()
        commands = [
            mapper.map_motion(_feature(timestamp_ms=60 + index, hand_velocity_norm=(0.004, 0.0)))
            for index in range(8)
        ]

        move_commands = [command for command in commands if command.type == "move_relative"]
        self.assertGreaterEqual(len(move_commands), 3)
        self.assertGreater(sum(abs(command.dx_px or 0) for command in move_commands), 0)


if __name__ == "__main__":
    unittest.main()
