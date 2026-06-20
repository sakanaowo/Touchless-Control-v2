import unittest

from tests.test_primitives import _feature


class CalibrationTests(unittest.TestCase):
    def test_named_sensitivity_presets_cover_gentle_balanced_and_responsive(self) -> None:
        from touchless_control.config import SensitivityPreset

        presets = SensitivityPreset.available()
        names = tuple(preset.name for preset in presets)

        self.assertEqual(names, ("gentle", "balanced", "responsive"))
        self.assertLess(SensitivityPreset.named("gentle").base_gain_px, SensitivityPreset.balanced().base_gain_px)
        self.assertGreater(
            SensitivityPreset.named("responsive").base_gain_px,
            SensitivityPreset.balanced().base_gain_px,
        )

    def test_calibration_profile_uses_samples_to_tune_thresholds_with_safe_bounds(self) -> None:
        from touchless_control.config import CalibrationService, SensitivityPreset

        base_preset = SensitivityPreset.balanced()
        samples = [
            _feature(
                timestamp_ms=1,
                palm_scale=0.50,
                palm_center_norm=(0.500, 0.500),
                pinch_ratio=0.62,
            ),
            _feature(
                timestamp_ms=2,
                palm_scale=0.52,
                palm_center_norm=(0.503, 0.500),
                pinch_ratio=0.29,
            ),
            _feature(
                timestamp_ms=3,
                palm_scale=0.51,
                palm_center_norm=(0.501, 0.504),
                pinch_ratio=0.58,
            ),
        ]

        profile = CalibrationService(base_preset).calibrate(samples, timestamp_ms=1_000)
        tuned = profile.to_preset(base_preset)

        self.assertEqual(profile.source_preset_name, "balanced")
        self.assertAlmostEqual(profile.palm_scale_baseline, 0.51)
        self.assertGreater(profile.jitter_norm, 0.0)
        self.assertLess(profile.pinch_close_ratio, profile.pinch_open_ratio)
        self.assertEqual(tuned.name, "balanced_calibrated")
        self.assertGreaterEqual(tuned.click_motion_guard, base_preset.click_motion_guard)


if __name__ == "__main__":
    unittest.main()
