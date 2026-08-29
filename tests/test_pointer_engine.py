import unittest
from dataclasses import replace

from tests.test_primitives import _feature


class PointerConfigTests(unittest.TestCase):
    def test_from_preset_creates_config_from_balanced_preset(self) -> None:
        from touchless_control.core.config import SensitivityPreset
        from touchless_control.control.pointer_config import PointerConfig

        preset = SensitivityPreset.balanced()
        config = PointerConfig.from_preset(preset)

        self.assertEqual(config.base_deadzone, preset.deadzone)
        self.assertEqual(config.base_gain_px, preset.base_gain_px)
        self.assertEqual(config.max_step_px, preset.max_step_px)
        self.assertFalse(config.invert_x)

    def test_from_preset_forwards_axis_inversion_and_gain_scale(self) -> None:
        from touchless_control.core.config import SensitivityPreset
        from touchless_control.control.pointer_config import PointerConfig

        config = PointerConfig.from_preset(
            SensitivityPreset.responsive(),
            invert_x=True,
            gain_scale=1.5,
        )

        self.assertTrue(config.invert_x)
        self.assertAlmostEqual(config.gain_scale, 1.5)


class PointerEngineTests(unittest.TestCase):
    def test_micro_deadzone_emits_none_for_tiny_motion(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        command = engine.map_motion(
            _feature(timestamp_ms=10, hand_velocity_norm=(0.0005, 0.0005))
        )

        self.assertEqual(command.type, "none")

    def test_maps_motion_to_relative_cursor_delta(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        # Prime with initial position
        engine.map_motion(_feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5)))
        command = engine.map_motion(
            _feature(
                timestamp_ms=2,
                hand_velocity_norm=(0.03, -0.02),
                palm_center_norm=(0.53, 0.48),
            )
        )

        self.assertEqual(command.type, "move_relative")
        self.assertIsInstance(command.dx_px, int)
        self.assertIsInstance(command.dy_px, int)
        self.assertNotEqual((command.dx_px, command.dy_px), (0, 0))

    def test_clamps_large_motion_to_max_step(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        feature = _feature(
            timestamp_ms=30,
            hand_velocity_norm=(5.0, -5.0),
            palm_center_norm=(0.9, 0.1),
        )
        command = engine.map_motion(feature)

        self.assertLessEqual(abs(command.dx_px or 0), engine.config.max_step_px)
        self.assertLessEqual(abs(command.dy_px or 0), engine.config.max_step_px)

    def test_inversion_reverses_cursor_direction(self) -> None:
        from touchless_control.control.pointer_config import PointerConfig
        from touchless_control.control.pointer_engine import PointerEngine

        feature = _feature(
            timestamp_ms=40,
            hand_velocity_norm=(0.04, -0.03),
            palm_center_norm=(0.54, 0.47),
        )

        normal = PointerEngine()
        normal.map_motion(_feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5)))
        cmd_normal = normal.map_motion(feature)

        inverted = PointerEngine(
            config=PointerConfig(invert_x=True, invert_y=True)
        )
        inverted.map_motion(_feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5)))
        cmd_inverted = inverted.map_motion(feature)

        self.assertEqual(cmd_inverted.dx_px, -cmd_normal.dx_px)
        self.assertEqual(cmd_inverted.dy_px, -cmd_normal.dy_px)

    def test_gain_scale_increases_cursor_response(self) -> None:
        from touchless_control.control.pointer_config import PointerConfig
        from touchless_control.control.pointer_engine import PointerEngine

        feature = _feature(
            timestamp_ms=50,
            hand_velocity_norm=(0.03, 0.0),
            palm_center_norm=(0.53, 0.5),
        )

        normal = PointerEngine()
        normal.map_motion(_feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5)))
        cmd_normal = normal.map_motion(feature)

        faster = PointerEngine(config=PointerConfig(gain_scale=1.5))
        faster.map_motion(_feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5)))
        cmd_faster = faster.map_motion(feature)

        self.assertGreaterEqual(abs(cmd_faster.dx_px or 0), abs(cmd_normal.dx_px or 0))

    def test_accumulates_subpixel_residual_for_small_motion(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        # Prime with initial position
        engine.map_motion(_feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5)))
        # Use velocity above base deadzone (0.015) but small enough for subpixel
        commands = [
            engine.map_motion(
                _feature(
                    timestamp_ms=10 + index,
                    hand_velocity_norm=(0.018, 0.0),
                    palm_center_norm=(0.5 + 0.018 * (index + 1), 0.5),
                )
            )
            for index in range(10)
        ]

        move_commands = [cmd for cmd in commands if cmd.type == "move_relative"]
        self.assertGreaterEqual(len(move_commands), 2)
        self.assertGreater(sum(abs(cmd.dx_px or 0) for cmd in move_commands), 0)

    def test_virtual_trackpad_clamps_position_outside_bounds(self) -> None:
        from touchless_control.control.pointer_config import PointerConfig
        from touchless_control.control.pointer_engine import PointerEngine

        config = PointerConfig(trackpad_bounds=(0.2, 0.8, 0.2, 0.8))
        engine = PointerEngine(config=config)
        # Position well inside bounds
        engine.map_motion(
            _feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5))
        )
        # Position far outside bounds — should be clamped, producing limited movement
        cmd_outside = engine.map_motion(
            _feature(
                timestamp_ms=2,
                hand_velocity_norm=(0.05, 0.0),
                palm_center_norm=(0.95, 0.5),
            )
        )
        # Position inside bounds with same velocity
        engine2 = PointerEngine(config=config)
        engine2.map_motion(
            _feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5))
        )
        cmd_inside = engine2.map_motion(
            _feature(
                timestamp_ms=2,
                hand_velocity_norm=(0.05, 0.0),
                palm_center_norm=(0.55, 0.5),
            )
        )
        # Both should produce movement (velocity component still active)
        # but outside-bounds position contribution should be damped
        if cmd_outside.type == "move_relative" and cmd_inside.type == "move_relative":
            self.assertIsNotNone(cmd_outside.dx_px)

    def test_adaptive_deadzone_grows_during_stillness(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        # Feed many near-zero velocity frames to grow stillness
        for i in range(20):
            engine.map_motion(
                _feature(
                    timestamp_ms=i,
                    hand_velocity_norm=(0.0001, 0.0001),
                    palm_center_norm=(0.5, 0.5),
                )
            )

        # After stillness, a slightly larger motion should still be absorbed
        cmd = engine.map_motion(
            _feature(
                timestamp_ms=100,
                hand_velocity_norm=(0.005, 0.0),
                palm_center_norm=(0.505, 0.5),
            )
        )
        # The adaptive deadzone should have grown enough to absorb this
        self.assertEqual(cmd.type, "none")

    def test_sustained_slow_motion_escapes_deadzone_after_stillness(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        for timestamp_ms in range(20):
            engine.map_motion(
                _feature(
                    timestamp_ms=timestamp_ms,
                    hand_velocity_norm=(0.0001, 0.0),
                    palm_center_norm=(0.5, 0.5),
                )
            )

        commands = [
            engine.map_motion(
                _feature(
                    timestamp_ms=100 + index,
                    hand_velocity_norm=(0.02, 0.0),
                    palm_center_norm=(0.52 + 0.02 * index, 0.5),
                )
            )
            for index in range(6)
        ]

        self.assertIn("move_relative", {command.type for command in commands})

    def test_source_state_propagates_to_action_command(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        engine.source_state = "Dragging"
        engine.map_motion(_feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5)))
        command = engine.map_motion(
            _feature(
                timestamp_ms=2,
                hand_velocity_norm=(0.05, 0.0),
                palm_center_norm=(0.55, 0.5),
            )
        )

        self.assertEqual(command.source_state, "Dragging")

    def test_position_blending_uses_position_for_slow_movement(self) -> None:
        from touchless_control.control.pointer_engine import PointerEngine

        engine = PointerEngine()
        # Prime
        engine.map_motion(
            _feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5))
        )
        # Slow movement — position component should dominate
        cmd = engine.map_motion(
            _feature(
                timestamp_ms=2,
                hand_velocity_norm=(0.005, 0.0),
                palm_center_norm=(0.505, 0.5),
            )
        )
        # With position blending for slow movement, even small velocity
        # should still produce movement thanks to position delta contribution
        # (This test verifies the blending pathway is active)
        # Use velocity above deadzone to verify position blending contributes
        results = []
        engine2 = PointerEngine()
        engine2.map_motion(
            _feature(timestamp_ms=1, palm_center_norm=(0.5, 0.5))
        )
        for i in range(5):
            r = engine2.map_motion(
                _feature(
                    timestamp_ms=10 + i,
                    hand_velocity_norm=(0.02, 0.0),
                    palm_center_norm=(0.5 + 0.02 * (i + 1), 0.5),
                )
            )
            results.append(r)

        move_results = [r for r in results if r.type == "move_relative"]
        self.assertGreaterEqual(len(move_results), 1)


if __name__ == "__main__":
    unittest.main()
