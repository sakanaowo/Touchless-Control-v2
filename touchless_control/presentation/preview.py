from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from touchless_control.core.contracts import ActionCommand, HandFrame, OSDispatchResult
from touchless_control.presentation.overlay import OverlaySnapshot


@dataclass(frozen=True, slots=True)
class PreviewStats:
    frames_read: int
    hand_frames: int
    commands_emitted: int
    dispatches: int
    failures: int
    fps: float


@dataclass(slots=True)
class OpenCVPreviewRenderer:
    window_name: str = "Touchless Control Preview"
    wait_key_ms: int = 1
    preview_width: int | None = None
    preview_height: int | None = None
    resizable: bool = True
    _window_ready: bool = field(default=False, init=False, repr=False)

    def render(
        self,
        frame: object,
        snapshot: OverlaySnapshot | None,
        *,
        commands: Sequence[ActionCommand] = (),
        results: Sequence[OSDispatchResult] = (),
        backend: str,
        dry_run: bool,
        hand_frame: HandFrame | None = None,
        stats: PreviewStats | None = None,
    ) -> bool:
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError("OpenCV is required for live preview") from error

        self._ensure_window(cv2)
        display = frame.copy() if hasattr(frame, "copy") else frame
        lines = _preview_lines(
            snapshot=snapshot,
            commands=commands,
            results=results,
            backend=backend,
            dry_run=dry_run,
            stats=stats,
        )
        for index, line in enumerate(lines):
            y = 24 + index * 24
            cv2.putText(
                display,
                line,
                (12, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                display,
                line,
                (12, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        if hand_frame is not None:
            _draw_hand_landmarks(cv2, display, hand_frame)

        _draw_action_badge(cv2, display, commands)

        cv2.imshow(self.window_name, display)
        key = cv2.waitKey(self.wait_key_ms) & 0xFF
        return key in {ord("q"), 27}

    def close(self) -> None:
        try:
            import cv2
        except ImportError:
            return
        cv2.destroyWindow(self.window_name)
        self._window_ready = False

    def _ensure_window(self, cv2: object) -> None:
        if self._window_ready:
            return
        if self.resizable and hasattr(cv2, "namedWindow"):
            flags = getattr(cv2, "WINDOW_NORMAL", 0) | getattr(cv2, "WINDOW_KEEPRATIO", 0)
            cv2.namedWindow(self.window_name, flags)
            if (
                self.preview_width is not None
                and self.preview_height is not None
                and hasattr(cv2, "resizeWindow")
            ):
                cv2.resizeWindow(
                    self.window_name,
                    self.preview_width,
                    self.preview_height,
                )
        self._window_ready = True


def _preview_lines(
    *,
    snapshot: OverlaySnapshot | None,
    commands: Sequence[ActionCommand],
    results: Sequence[OSDispatchResult],
    backend: str,
    dry_run: bool,
    stats: PreviewStats | None = None,
) -> tuple[str, ...]:
    mode = "dry_run" if dry_run else "dispatch"
    command_text = ",".join(command.type for command in commands) or "-"
    failure_count = sum(1 for result in results if not result.success)
    stats_line = _stats_line(stats)
    if snapshot is None:
        lines = [
            f"mode={mode} backend={backend}",
            "state=NoHand tracking=no_hand",
            f"commands={command_text} failures={failure_count}",
            "press q or Esc to quit",
        ]
        if stats_line is not None:
            lines.insert(1, stats_line)
        return tuple(lines)

    latency = "-" if snapshot.latency_ms is None else f"{snapshot.latency_ms:.1f}ms"
    lines = [
        f"mode={mode} backend={backend}",
        f"state={snapshot.state} active={snapshot.active_mode} tracking={snapshot.tracking_status}",
        f"pinch={snapshot.pinch_ratio:.3f} stability={snapshot.stability_score:.2f} latency={latency}",
        f"commands={command_text} failures={failure_count}",
        "press q or Esc to quit",
    ]
    if stats_line is not None:
        lines.insert(1, stats_line)
    return tuple(lines)


def _draw_hand_landmarks(cv2: object, display: object, hand_frame: HandFrame) -> None:
    display_width, display_height = _display_dimensions(display, hand_frame)
    points = [
        (
            int(x * display_width),
            int(y * display_height),
        )
        for x, y, _z in hand_frame.landmarks_img
    ]
    for start, end in _HAND_CONNECTIONS:
        if start < len(points) and end < len(points):
            cv2.line(display, points[start], points[end], (64, 220, 255), 2, cv2.LINE_AA)
    if len(points) > 8:
        thumb_tip = points[4]
        index_tip = points[8]
        pinch_center = (
            (thumb_tip[0] + index_tip[0]) // 2,
            (thumb_tip[1] + index_tip[1]) // 2,
        )
        cv2.line(display, thumb_tip, index_tip, (255, 0, 255), 3, cv2.LINE_AA)
        cv2.circle(display, pinch_center, 6, (255, 0, 255), -1, cv2.LINE_AA)
    for point in points:
        cv2.circle(display, point, 4, (40, 240, 120), -1, cv2.LINE_AA)


def _display_dimensions(display: object, hand_frame: HandFrame) -> tuple[int, int]:
    shape = getattr(display, "shape", None)
    if shape is not None and len(shape) >= 2:
        return int(shape[1]), int(shape[0])
    return hand_frame.image_width, hand_frame.image_height


def _stats_line(stats: PreviewStats | None) -> str | None:
    if stats is None:
        return None
    return (
        f"fps={stats.fps:.1f} frames={stats.frames_read} hands={stats.hand_frames} "
        f"commands={stats.commands_emitted} dispatches={stats.dispatches} failures={stats.failures}"
    )


def _draw_action_badge(
    cv2: object,
    display: object,
    commands: Sequence[ActionCommand],
) -> None:
    if not commands:
        return
    action = commands[-1].type
    cv2.rectangle(display, (12, 138), (260, 178), (0, 0, 0), -1)
    cv2.putText(
        display,
        f"ACTION {action}",
        (22, 164),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )


_HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (0, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (0, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
)
