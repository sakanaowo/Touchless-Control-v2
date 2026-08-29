from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Sequence

from touchless_control.core.config import SensitivityPreset
from touchless_control.core.contracts import FeatureFrame, Point2D

ControlRegion = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class PointerCalibrationProfile:
    source_preset_name: str
    created_at_ms: int
    neutral_center_norm: Point2D
    jitter_norm: float
    deadzone_norm: float
    control_region: ControlRegion
    gain_scale: float
    direction_validated: bool = False
    invert_x: bool = False
    invert_y: bool = False


@dataclass(frozen=True, slots=True)
class PointerCalibrationService:
    preset: SensitivityPreset
    minimum_control_span: float = 0.10
    reference_control_span: float = 0.70
    minimum_direction_travel: float = 0.05

    def calibrate(
        self,
        *,
        neutral_samples: Sequence[FeatureFrame],
        control_samples: Sequence[FeatureFrame],
        horizontal_samples: Sequence[FeatureFrame] = (),
        vertical_samples: Sequence[FeatureFrame] = (),
        expected_x_direction: int = 1,
        expected_y_direction: int = 1,
        timestamp_ms: int,
    ) -> PointerCalibrationProfile:
        if not neutral_samples:
            raise ValueError("Pointer calibration requires neutral samples")
        if not control_samples:
            raise ValueError("Pointer calibration requires control-region samples")

        neutral_center = _median_point(neutral_samples)
        jitter = _rms_distance(neutral_samples, neutral_center)
        control_region = _control_region(control_samples)
        x_min, x_max, y_min, y_max = control_region
        x_span = x_max - x_min
        y_span = y_max - y_min
        if x_span < self.minimum_control_span or y_span < self.minimum_control_span:
            raise ValueError("Pointer calibration control region is too small")

        observed_span = (x_span + y_span) / 2.0
        gain_scale = _clamp(self.reference_control_span / observed_span, 0.75, 2.50)
        deadzone = _clamp(
            max(self.preset.deadzone, jitter * 3.0),
            self.preset.deadzone,
            0.05,
        )
        direction_validated = bool(horizontal_samples or vertical_samples)
        if direction_validated and not (horizontal_samples and vertical_samples):
            raise ValueError("Pointer direction validation requires both axes")
        invert_x = False
        invert_y = False
        if direction_validated:
            invert_x = _axis_requires_inversion(
                horizontal_samples,
                axis=0,
                expected_direction=expected_x_direction,
                minimum_travel=self.minimum_direction_travel,
            )
            invert_y = _axis_requires_inversion(
                vertical_samples,
                axis=1,
                expected_direction=expected_y_direction,
                minimum_travel=self.minimum_direction_travel,
            )
        return PointerCalibrationProfile(
            source_preset_name=self.preset.name,
            created_at_ms=timestamp_ms,
            neutral_center_norm=neutral_center,
            jitter_norm=jitter,
            deadzone_norm=deadzone,
            control_region=control_region,
            gain_scale=gain_scale,
            direction_validated=direction_validated,
            invert_x=invert_x,
            invert_y=invert_y,
        )


def _median_point(samples: Sequence[FeatureFrame]) -> Point2D:
    return (
        float(median(sample.palm_center_norm[0] for sample in samples)),
        float(median(sample.palm_center_norm[1] for sample in samples)),
    )


def _rms_distance(samples: Sequence[FeatureFrame], center: Point2D) -> float:
    mean_squared_distance = sum(
        math.dist(sample.palm_center_norm, center) ** 2 for sample in samples
    ) / len(samples)
    return math.sqrt(mean_squared_distance)


def _control_region(samples: Sequence[FeatureFrame]) -> ControlRegion:
    xs = [sample.palm_center_norm[0] for sample in samples]
    ys = [sample.palm_center_norm[1] for sample in samples]
    return (min(xs), max(xs), min(ys), max(ys))


def _axis_requires_inversion(
    samples: Sequence[FeatureFrame],
    *,
    axis: int,
    expected_direction: int,
    minimum_travel: float,
) -> bool:
    if expected_direction not in {-1, 1}:
        raise ValueError("Expected pointer direction must be -1 or 1")
    if len(samples) < 2:
        raise ValueError("Pointer direction validation requires at least two samples")
    observed_delta = (
        samples[-1].palm_center_norm[axis] - samples[0].palm_center_norm[axis]
    )
    if abs(observed_delta) < minimum_travel:
        raise ValueError("Pointer direction validation movement is too small")
    observed_direction = 1 if observed_delta > 0 else -1
    return observed_direction != expected_direction


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
