from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from touchless_control.core.contracts import FeatureFrame


@dataclass(frozen=True, slots=True)
class SensitivityPreset:
    name: str
    deadzone: float
    base_gain_px: int
    accel_gain_px: int
    v_ref: float
    gamma: float
    ema_alpha_slow: float
    ema_alpha_fast: float
    max_step_px: int
    pinch_close_ratio: float
    pinch_open_ratio: float
    drag_hold_threshold_ms: int
    click_motion_guard: float
    early_drag_motion_threshold: float
    scroll_interval_ms: int

    @classmethod
    def gentle(cls) -> SensitivityPreset:
        return cls(
            name="gentle",
            deadzone=0.020,
            base_gain_px=650,
            accel_gain_px=1100,
            v_ref=0.12,
            gamma=1.7,
            ema_alpha_slow=0.18,
            ema_alpha_fast=0.45,
            max_step_px=90,
            pinch_close_ratio=0.28,
            pinch_open_ratio=0.46,
            drag_hold_threshold_ms=330,
            click_motion_guard=0.05,
            early_drag_motion_threshold=0.14,
            scroll_interval_ms=120,
        )

    @classmethod
    def balanced(cls) -> SensitivityPreset:
        return cls(
            name="balanced",
            deadzone=0.015,
            base_gain_px=900,
            accel_gain_px=1600,
            v_ref=0.10,
            gamma=1.6,
            ema_alpha_slow=0.22,
            ema_alpha_fast=0.55,
            max_step_px=120,
            pinch_close_ratio=0.30,
            pinch_open_ratio=0.45,
            drag_hold_threshold_ms=280,
            click_motion_guard=0.04,
            early_drag_motion_threshold=0.12,
            scroll_interval_ms=100,
        )

    @classmethod
    def responsive(cls) -> SensitivityPreset:
        return cls(
            name="responsive",
            deadzone=0.010,
            base_gain_px=1150,
            accel_gain_px=2100,
            v_ref=0.09,
            gamma=1.5,
            ema_alpha_slow=0.30,
            ema_alpha_fast=0.65,
            max_step_px=150,
            pinch_close_ratio=0.32,
            pinch_open_ratio=0.44,
            drag_hold_threshold_ms=240,
            click_motion_guard=0.035,
            early_drag_motion_threshold=0.10,
            scroll_interval_ms=80,
        )

    @classmethod
    def available(cls) -> tuple[SensitivityPreset, ...]:
        return (cls.gentle(), cls.balanced(), cls.responsive())

    @classmethod
    def named(cls, name: str) -> SensitivityPreset:
        for preset in cls.available():
            if preset.name == name:
                return preset
        raise ValueError(f"Unknown sensitivity preset: {name}")


@dataclass(frozen=True, slots=True)
class CalibrationProfile:
    source_preset_name: str
    created_at_ms: int
    palm_scale_baseline: float
    jitter_norm: float
    pinch_close_ratio: float
    pinch_open_ratio: float
    click_motion_guard: float
    early_drag_motion_threshold: float

    def to_preset(self, base_preset: SensitivityPreset) -> SensitivityPreset:
        return replace(
            base_preset,
            name=f"{base_preset.name}_calibrated",
            pinch_close_ratio=self.pinch_close_ratio,
            pinch_open_ratio=self.pinch_open_ratio,
            click_motion_guard=self.click_motion_guard,
            early_drag_motion_threshold=self.early_drag_motion_threshold,
        )


@dataclass(frozen=True, slots=True)
class CalibrationService:
    preset: SensitivityPreset

    def calibrate(
        self,
        samples: Sequence[FeatureFrame],
        *,
        timestamp_ms: int,
    ) -> CalibrationProfile:
        if not samples:
            raise ValueError("Calibration requires at least one feature sample")

        pinch_ratios = [sample.pinch_ratio for sample in samples]
        close_upper = min(0.40, self.preset.pinch_open_ratio - 0.05)
        pinch_close = _clamp(min(pinch_ratios) + 0.02, 0.20, close_upper)
        pinch_open = _clamp(
            max(max(pinch_ratios) - 0.04, pinch_close + 0.10),
            pinch_close + 0.10,
            0.75,
        )
        jitter = _average_motion(sample.palm_center_norm for sample in samples)
        click_guard = _clamp(
            self.preset.click_motion_guard + (jitter * 2.0),
            self.preset.click_motion_guard,
            0.09,
        )

        return CalibrationProfile(
            source_preset_name=self.preset.name,
            created_at_ms=timestamp_ms,
            palm_scale_baseline=_median(sample.palm_scale for sample in samples),
            jitter_norm=jitter,
            pinch_close_ratio=pinch_close,
            pinch_open_ratio=pinch_open,
            click_motion_guard=click_guard,
            early_drag_motion_threshold=_clamp(
                self.preset.early_drag_motion_threshold + (jitter * 4.0),
                max(self.preset.early_drag_motion_threshold, click_guard + 0.02),
                0.20,
            ),
        )


def _median(values: Iterable[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _average_motion(points: Iterable[tuple[float, float]]) -> float:
    ordered = list(points)
    if len(ordered) < 2:
        return 0.0
    distances = [
        math.dist(ordered[index - 1], ordered[index])
        for index in range(1, len(ordered))
    ]
    return sum(distances) / len(distances)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
