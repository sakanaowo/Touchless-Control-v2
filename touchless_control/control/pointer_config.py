from __future__ import annotations

from dataclasses import dataclass, replace

from touchless_control.control.pointer_calibration import PointerCalibrationProfile
from touchless_control.core.config import SensitivityPreset


@dataclass(frozen=True, slots=True)
class PointerConfig:
    """Configuration for the product-grade pointer engine.

    Groups all tuning parameters for position-velocity blending,
    adaptive deadzone, virtual trackpad bounds, gain curves,
    smoothing, and step clamping.
    """

    # Deadzone
    base_deadzone: float = 0.015
    max_deadzone: float = 0.035
    micro_deadzone_scale: float = 0.20
    stillness_decay: float = 0.05
    motion_stop_frames: int = 3
    quiet_motion_decay: float = 0.55

    # Position-velocity blending
    blend_v_ref: float = 0.04

    # Virtual trackpad bounds (x_min, x_max, y_min, y_max) in normalized space
    trackpad_bounds: tuple[float, float, float, float] = (0.15, 0.85, 0.15, 0.85)

    # Gain curve
    base_gain_px: int = 900
    accel_gain_px: int = 1600
    v_ref: float = 0.10
    gamma: float = 1.6

    # Smoothing
    ema_alpha_slow: float = 0.22
    ema_alpha_fast: float = 0.55

    # Step clamping
    max_step_px: int = 120

    # Axis inversion
    invert_x: bool = False
    invert_y: bool = False

    # Gain scaling
    gain_scale: float = 1.0

    @classmethod
    def from_preset(
        cls,
        preset: SensitivityPreset,
        *,
        invert_x: bool = False,
        invert_y: bool = False,
        gain_scale: float = 1.0,
    ) -> PointerConfig:
        """Create a PointerConfig from an existing SensitivityPreset."""
        return cls(
            base_deadzone=preset.deadzone,
            max_deadzone=preset.deadzone * 2.5,
            micro_deadzone_scale=0.20,
            stillness_decay=0.05,
            motion_stop_frames=3,
            quiet_motion_decay=0.55,
            blend_v_ref=preset.v_ref * 0.4,
            trackpad_bounds=(0.15, 0.85, 0.15, 0.85),
            base_gain_px=preset.base_gain_px,
            accel_gain_px=preset.accel_gain_px,
            v_ref=preset.v_ref,
            gamma=preset.gamma,
            ema_alpha_slow=preset.ema_alpha_slow,
            ema_alpha_fast=preset.ema_alpha_fast,
            max_step_px=preset.max_step_px,
            invert_x=invert_x,
            invert_y=invert_y,
            gain_scale=gain_scale,
        )

    @classmethod
    def from_calibration(
        cls,
        preset: SensitivityPreset,
        profile: PointerCalibrationProfile,
        *,
        gain_scale: float = 1.0,
    ) -> PointerConfig:
        base = cls.from_preset(
            preset,
            invert_x=profile.invert_x,
            invert_y=profile.invert_y,
            gain_scale=gain_scale * profile.gain_scale,
        )
        return replace(
            base,
            base_deadzone=profile.deadzone_norm,
            max_deadzone=min(0.08, profile.deadzone_norm * 2.5),
            trackpad_bounds=profile.control_region,
        )
