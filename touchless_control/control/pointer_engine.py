from __future__ import annotations

import math
from dataclasses import dataclass, field

from touchless_control.control.pointer_config import PointerConfig
from touchless_control.core.contracts import ActionCommand, FeatureFrame, Point2D


@dataclass(slots=True)
class PointerEngine:
    """Product-grade pointer engine combining position-velocity blending,
    adaptive deadzone, virtual trackpad bounds, and residual accumulation.

    Drop-in replacement for CursorMapper.map_motion().
    """

    config: PointerConfig = field(default_factory=PointerConfig)
    source_state: str = "Pointing"
    _filtered_velocity: Point2D = (0.0, 0.0)
    _residual_px: Point2D = (0.0, 0.0)
    _previous_position: Point2D | None = None
    _stillness_frames: int = 0

    def map_motion(self, feature_frame: FeatureFrame) -> ActionCommand:
        velocity = feature_frame.hand_velocity_norm
        position = feature_frame.palm_center_norm
        speed = math.hypot(*velocity)

        # Clamp position to virtual trackpad bounds
        clamped_position = _clamp_to_bounds(position, self.config.trackpad_bounds)

        # Compute position delta
        position_delta = _delta(clamped_position, self._previous_position)
        self._previous_position = clamped_position

        # Adaptive deadzone: grows during stillness, shrinks when moving
        active_deadzone = self._adaptive_deadzone(speed)

        if speed < active_deadzone:
            self._stillness_frames += 1
            self._filtered_velocity = (0.0, 0.0)
            self._residual_px = (0.0, 0.0)
            return ActionCommand.none(
                timestamp_ms=feature_frame.timestamp_ms,
                source_state=self.source_state,
            )

        self._stillness_frames = 0

        # Blend position and velocity based on speed
        blended = _blend(
            position_delta=position_delta,
            velocity=velocity,
            speed=speed,
            blend_v_ref=self.config.blend_v_ref,
        )

        # Adaptive EMA smoothing
        alpha = self._adaptive_alpha(speed)
        self._filtered_velocity = (
            self._filtered_velocity[0] + alpha * (blended[0] - self._filtered_velocity[0]),
            self._filtered_velocity[1] + alpha * (blended[1] - self._filtered_velocity[1]),
        )

        # Gain curve
        gain = self._gain(speed)

        # Apply gain and accumulate residual
        dx_px, residual_x = _split_step(
            gain * self._filtered_velocity[0] + self._residual_px[0],
            self.config.max_step_px,
        )
        dy_px, residual_y = _split_step(
            gain * self._filtered_velocity[1] + self._residual_px[1],
            self.config.max_step_px,
        )
        self._residual_px = (residual_x, residual_y)

        # Axis inversion
        if self.config.invert_x:
            dx_px = -dx_px
        if self.config.invert_y:
            dy_px = -dy_px

        if dx_px == 0 and dy_px == 0:
            return ActionCommand.none(
                timestamp_ms=feature_frame.timestamp_ms,
                source_state=self.source_state,
            )

        return ActionCommand.move_relative(
            timestamp_ms=feature_frame.timestamp_ms,
            dx_px=dx_px,
            dy_px=dy_px,
            source_state=self.source_state,
        )

    def _adaptive_deadzone(self, speed: float) -> float:
        """Deadzone grows when the hand is still, shrinks when moving."""
        base = self.config.base_deadzone
        micro = base * self.config.micro_deadzone_scale
        if speed >= base:
            return base
        stillness_factor = min(self._stillness_frames * self.config.stillness_decay, 3.0)
        active = base * (1.0 + stillness_factor)
        return max(micro, min(active, self.config.max_deadzone))

    def _adaptive_alpha(self, speed: float) -> float:
        ratio = min(speed / self.config.v_ref, 1.0)
        return self.config.ema_alpha_slow + (
            self.config.ema_alpha_fast - self.config.ema_alpha_slow
        ) * ratio

    def _gain(self, speed: float) -> float:
        ratio = min(speed / self.config.v_ref, 1.0)
        gain = self.config.base_gain_px + self.config.accel_gain_px * (ratio ** self.config.gamma)
        return gain * self.config.gain_scale


def _clamp_to_bounds(
    position: Point2D,
    bounds: tuple[float, float, float, float],
) -> Point2D:
    """Clamp a position to virtual trackpad bounds (x_min, x_max, y_min, y_max)."""
    x_min, x_max, y_min, y_max = bounds
    return (
        max(x_min, min(x_max, position[0])),
        max(y_min, min(y_max, position[1])),
    )


def _delta(current: Point2D, previous: Point2D | None) -> Point2D:
    if previous is None:
        return (0.0, 0.0)
    return (current[0] - previous[0], current[1] - previous[1])


def _blend(
    *,
    position_delta: Point2D,
    velocity: Point2D,
    speed: float,
    blend_v_ref: float,
) -> Point2D:
    """Blend position delta and velocity based on speed.

    At low speed, position delta dominates (more stable).
    At high speed, velocity dominates (more responsive).
    """
    blend_ratio = min(speed / max(blend_v_ref, 1e-9), 1.0)
    return (
        position_delta[0] * (1.0 - blend_ratio) + velocity[0] * blend_ratio,
        position_delta[1] * (1.0 - blend_ratio) + velocity[1] * blend_ratio,
    )


def _split_step(value: float, max_step: int) -> tuple[int, float]:
    step = int(value)
    if step > max_step:
        return max_step, 0.0
    if step < -max_step:
        return -max_step, 0.0
    return step, value - step
