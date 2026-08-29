import unittest

from tests.test_primitives import _feature


class PointerCalibrationTests(unittest.TestCase):
    def test_exports_pointer_calibration_api_from_control_package(self) -> None:
        from touchless_control.control import (
            PointerCalibrationProfile,
            PointerCalibrationService,
        )

        self.assertEqual(PointerCalibrationProfile.__name__, "PointerCalibrationProfile")
        self.assertEqual(PointerCalibrationService.__name__, "PointerCalibrationService")

    def test_derives_neutral_zone_and_control_region_from_samples(self) -> None:
        from touchless_control.control.pointer_calibration import (
            PointerCalibrationService,
        )
        from touchless_control.core.config import SensitivityPreset

        neutral_samples = [
            _feature(timestamp_ms=1, palm_center_norm=(0.49, 0.50)),
            _feature(timestamp_ms=2, palm_center_norm=(0.50, 0.51)),
            _feature(timestamp_ms=3, palm_center_norm=(0.51, 0.49)),
        ]
        control_samples = [
            _feature(timestamp_ms=10, palm_center_norm=(0.20, 0.25)),
            _feature(timestamp_ms=11, palm_center_norm=(0.80, 0.25)),
            _feature(timestamp_ms=12, palm_center_norm=(0.20, 0.75)),
            _feature(timestamp_ms=13, palm_center_norm=(0.80, 0.75)),
        ]

        profile = PointerCalibrationService(SensitivityPreset.balanced()).calibrate(
            neutral_samples=neutral_samples,
            control_samples=control_samples,
            timestamp_ms=1_000,
        )

        self.assertEqual(profile.created_at_ms, 1_000)
        self.assertEqual(profile.neutral_center_norm, (0.50, 0.50))
        self.assertEqual(profile.control_region, (0.20, 0.80, 0.25, 0.75))
        self.assertGreaterEqual(profile.deadzone_norm, profile.jitter_norm)
        self.assertGreater(profile.gain_scale, 1.0)

    def test_validates_direction_and_marks_required_axis_inversion(self) -> None:
        from touchless_control.control.pointer_calibration import (
            PointerCalibrationService,
        )
        from touchless_control.core.config import SensitivityPreset

        neutral_samples = [
            _feature(timestamp_ms=1, palm_center_norm=(0.50, 0.50)),
            _feature(timestamp_ms=2, palm_center_norm=(0.51, 0.50)),
        ]
        control_samples = [
            _feature(timestamp_ms=10, palm_center_norm=(0.20, 0.20)),
            _feature(timestamp_ms=11, palm_center_norm=(0.80, 0.80)),
        ]
        horizontal_samples = [
            _feature(timestamp_ms=20, palm_center_norm=(0.70, 0.50)),
            _feature(timestamp_ms=21, palm_center_norm=(0.30, 0.50)),
        ]
        vertical_samples = [
            _feature(timestamp_ms=30, palm_center_norm=(0.50, 0.30)),
            _feature(timestamp_ms=31, palm_center_norm=(0.50, 0.70)),
        ]

        profile = PointerCalibrationService(SensitivityPreset.balanced()).calibrate(
            neutral_samples=neutral_samples,
            control_samples=control_samples,
            horizontal_samples=horizontal_samples,
            vertical_samples=vertical_samples,
            expected_x_direction=1,
            expected_y_direction=1,
            timestamp_ms=2_000,
        )

        self.assertTrue(profile.direction_validated)
        self.assertTrue(profile.invert_x)
        self.assertFalse(profile.invert_y)

    def test_applies_calibration_profile_to_pointer_config(self) -> None:
        from touchless_control.control.pointer_calibration import (
            PointerCalibrationProfile,
        )
        from touchless_control.control.pointer_config import PointerConfig
        from touchless_control.core.config import SensitivityPreset

        profile = PointerCalibrationProfile(
            source_preset_name="balanced",
            created_at_ms=3_000,
            neutral_center_norm=(0.5, 0.5),
            jitter_norm=0.006,
            deadzone_norm=0.018,
            control_region=(0.2, 0.8, 0.25, 0.75),
            gain_scale=1.2,
            direction_validated=True,
            invert_x=True,
            invert_y=False,
        )

        config = PointerConfig.from_calibration(
            SensitivityPreset.balanced(),
            profile,
            gain_scale=1.25,
        )

        self.assertEqual(config.base_deadzone, 0.018)
        self.assertEqual(config.trackpad_bounds, profile.control_region)
        self.assertTrue(config.invert_x)
        self.assertFalse(config.invert_y)
        self.assertAlmostEqual(config.gain_scale, 1.5)


if __name__ == "__main__":
    unittest.main()
