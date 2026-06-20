from __future__ import annotations

import math
from dataclasses import dataclass, field

from touchless_control.core.config import SensitivityPreset
from touchless_control.core.contracts import ActionCommand, FeatureFrame, Point2D


@dataclass(slots=True)
class CursorMapper:
    preset: SensitivityPreset = field(default_factory=SensitivityPreset.balanced)
    source_state: str = "Pointing"
    _filtered_velocity: Point2D = (0.0, 0.0)

    def map_motion(self, feature_frame: FeatureFrame) -> ActionCommand:
        velocity = feature_frame.hand_velocity_norm
        speed = math.hypot(*velocity)
        if speed < self.preset.deadzone:
            self._filtered_velocity = (0.0, 0.0)
            return ActionCommand.none(
                timestamp_ms=feature_frame.timestamp_ms,
                source_state=self.source_state,
            )

        alpha = self._adaptive_alpha(speed)
        self._filtered_velocity = (
            self._filtered_velocity[0] + alpha * (velocity[0] - self._filtered_velocity[0]),
            self._filtered_velocity[1] + alpha * (velocity[1] - self._filtered_velocity[1]),
        )
        gain = self._gain(speed)
        dx_px = _clamp_step(round(gain * self._filtered_velocity[0]), self.preset.max_step_px)
        dy_px = _clamp_step(round(gain * self._filtered_velocity[1]), self.preset.max_step_px)

        return ActionCommand.move_relative(
            timestamp_ms=feature_frame.timestamp_ms,
            dx_px=dx_px,
            dy_px=dy_px,
            source_state=self.source_state,
        )

    def _adaptive_alpha(self, speed: float) -> float:
        ratio = min(speed / self.preset.v_ref, 1.0)
        return self.preset.ema_alpha_slow + (
            self.preset.ema_alpha_fast - self.preset.ema_alpha_slow
        ) * ratio

    def _gain(self, speed: float) -> float:
        ratio = min(speed / self.preset.v_ref, 1.0)
        return self.preset.base_gain_px + self.preset.accel_gain_px * (ratio**self.preset.gamma)


def _clamp_step(value: int, max_step: int) -> int:
    return max(-max_step, min(max_step, value))
