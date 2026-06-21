from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, dataclass, field
from os import environ
from typing import Any, Callable, Protocol, Sequence

from touchless_control.control.os.base import MouseController
from touchless_control.control.os.factory import create_mouse_controller
from touchless_control.control.cursor import CursorMapper
from touchless_control.core.config import SensitivityPreset
from touchless_control.core.contracts import ActionCommand, OSDispatchResult
from touchless_control.interaction import InteractionStateMachine, PrimitiveDetector
from touchless_control.observability import SessionLogger
from touchless_control.presentation import (
    OpenCVPreviewRenderer,
    OverlayPresenter,
    OverlaySnapshot,
    PreviewStats,
)
from touchless_control.runtime.pipeline import TouchlessPipeline
from touchless_control.vision.camera import (
    CaptureFactory,
    FrameConverter,
    PerceptionFactory,
    SleepFn,
    TimestampClock,
    _default_capture_factory,
    _default_frame_converter,
    _now_ms,
    _sleep_ms,
)
from touchless_control.vision.hands.features import FeatureNormalizer
from touchless_control.vision.hands.mediapipe import (
    MediaPipeHandPerception,
    create_mediapipe_detector_factory,
)

ControllerFactory = Callable[[], MouseController]
LogWriter = Callable[[str, str], None]


class PreviewRenderer(Protocol):
    def render(
        self,
        frame: object,
        snapshot: OverlaySnapshot | None,
        *,
        commands: Sequence[ActionCommand],
        results: Sequence[OSDispatchResult],
        backend: str,
        dry_run: bool,
        hand_frame: object | None = None,
        stats: PreviewStats | None = None,
    ) -> bool:
        ...

    def close(self) -> None:
        ...


def _default_log_writer(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as log_file:
        log_file.write(content)


@dataclass(frozen=True, slots=True)
class LiveRunResult:
    success: bool
    frames_read: int
    hand_frames: int
    commands_emitted: int
    dispatches: int
    failures: int
    read_failures: int = 0
    backend: str = ""
    log_records: int = 0
    preview_frames: int = 0
    average_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    log_path: str | None = None
    error_code: str | None = None


@dataclass(slots=True)
class LiveRunner:
    camera_index: int = 0
    image_width: int = 640
    image_height: int = 480
    model_asset_path: str | None = None
    dry_run: bool = False
    preview: bool = False
    preview_width: int = 960
    preview_height: int = 720
    camera_fps: int = 60
    camera_buffer_size: int = 1
    preset_name: str = "responsive"
    invert_x: bool = True
    invert_y: bool = False
    cursor_gain_scale: float = 1.25
    max_read_failures: int = 10
    suppress_native_logs: bool = True
    capture_factory: CaptureFactory = _default_capture_factory
    perception_factory: PerceptionFactory | None = None
    frame_converter: FrameConverter = _default_frame_converter
    timestamp_ms: TimestampClock = _now_ms
    poll_timeout_ms: int = 20
    poll_interval_ms: int = 2
    sleep_ms: SleepFn = _sleep_ms
    normalizer: FeatureNormalizer = field(default_factory=FeatureNormalizer)
    pipeline: TouchlessPipeline | None = None
    controller_factory: ControllerFactory = create_mouse_controller
    logger: SessionLogger = field(default_factory=SessionLogger)
    log_path: str | None = None
    log_writer: LogWriter = _default_log_writer
    overlay: OverlayPresenter = field(default_factory=OverlayPresenter)
    preview_renderer: PreviewRenderer | None = None

    def run(self, *, max_frames: int = 0) -> LiveRunResult:
        capture = self.capture_factory(self.camera_index)
        if not capture.isOpened():
            return LiveRunResult(
                success=False,
                frames_read=0,
                hand_frames=0,
                commands_emitted=0,
                dispatches=0,
                failures=0,
                read_failures=0,
                backend="dry_run" if self.dry_run else "",
                log_path=self.log_path,
                error_code="camera_open_failed",
            )
        self._configure_capture(capture)

        frames_read = 0
        read_failures = 0
        consecutive_read_failures = 0
        hand_frames = 0
        commands_emitted = 0
        dispatches = 0
        failures = 0
        preview_frames = 0
        controller = self._create_controller()
        preview_renderer = self._create_preview_renderer()
        stop_requested = False
        frame_limit = None if max_frames <= 0 else max_frames
        started_at_ms: int | None = None
        terminal_error_code: str | None = None
        last_hand_timestamp_ms: int | None = None
        pipeline = self.pipeline or _create_pipeline(
            preset_name=self.preset_name,
            invert_x=self.invert_x,
            invert_y=self.invert_y,
            gain_scale=self.cursor_gain_scale,
        )
        try:
            perception_factory = self.perception_factory or self._create_default_perception
            with _native_log_sink(self.suppress_native_logs):
                perception = perception_factory(self.image_width, self.image_height)
                while (frame_limit is None or frames_read < frame_limit) and not stop_requested:
                    ok, frame = capture.read()
                    if not ok:
                        read_failures += 1
                        consecutive_read_failures += 1
                        if consecutive_read_failures >= max(1, self.max_read_failures):
                            terminal_error_code = (
                                "camera_read_failed"
                                if frames_read == 0
                                else "camera_read_interrupted"
                            )
                            break
                        self.sleep_ms(self.poll_interval_ms)
                        continue

                    timestamp_ms = self.timestamp_ms()
                    if started_at_ms is None:
                        started_at_ms = timestamp_ms
                    frames_read += 1
                    consecutive_read_failures = 0
                    perception.submit(self.frame_converter(frame), timestamp_ms)
                    hand_frame = self._poll_latest_hand(perception)
                    if hand_frame is None:
                        if preview_renderer is not None:
                            preview_frames += 1
                            stop_requested = preview_renderer.render(
                                frame,
                                None,
                                commands=(),
                                results=(),
                                backend=controller.backend_name,
                                dry_run=self.dry_run,
                                hand_frame=None,
                                stats=_preview_stats(
                                    frames_read=frames_read,
                                    hand_frames=hand_frames,
                                    commands_emitted=commands_emitted,
                                    dispatches=dispatches,
                                    failures=failures,
                                    started_at_ms=started_at_ms,
                                    now_ms=timestamp_ms,
                                ),
                        )
                        continue

                    feature_frame = self.normalizer.to_features(hand_frame)
                    hand_timestamp_ms = int(
                        getattr(hand_frame, "timestamp_ms", feature_frame.timestamp_ms)
                    )
                    if (
                        last_hand_timestamp_ms is not None
                        and hand_timestamp_ms <= last_hand_timestamp_ms
                    ):
                        if preview_renderer is not None:
                            preview_frames += 1
                            stop_requested = preview_renderer.render(
                                frame,
                                None,
                                commands=(),
                                results=(),
                                backend=controller.backend_name,
                                dry_run=self.dry_run,
                                hand_frame=None,
                                stats=_preview_stats(
                                    frames_read=frames_read,
                                    hand_frames=hand_frames,
                                    commands_emitted=commands_emitted,
                                    dispatches=dispatches,
                                    failures=failures,
                                    started_at_ms=started_at_ms,
                                    now_ms=timestamp_ms,
                                ),
                            )
                        continue

                    last_hand_timestamp_ms = hand_timestamp_ms
                    hand_frames += 1
                    commands = pipeline.step(feature_frame)
                    commands_emitted += len(commands)
                    results = pipeline.flush(controller)
                    dispatches += len(results)
                    failures += sum(1 for result in results if not result.success)
                    latency_ms = float(max(0, self.timestamp_ms() - feature_frame.timestamp_ms))
                    self.logger.record(
                        feature_frame=feature_frame,
                        primitive_events=tuple(
                            getattr(pipeline, "last_primitive_events", ())
                        ),
                        interaction_events=tuple(
                            getattr(pipeline, "last_interaction_events", ())
                        ),
                        commands=commands,
                        results=results,
                        latency_ms=latency_ms,
                    )
                    if preview_renderer is not None:
                        snapshot = self.overlay.snapshot(
                            feature_frame=feature_frame,
                            state=_pipeline_state(pipeline, commands),
                            latency_ms=latency_ms,
                        )
                        preview_frames += 1
                        stop_requested = preview_renderer.render(
                            frame,
                            snapshot,
                            commands=commands,
                            results=results,
                            backend=controller.backend_name,
                            dry_run=self.dry_run,
                            hand_frame=hand_frame,
                            stats=_preview_stats(
                                frames_read=frames_read,
                                hand_frames=hand_frames,
                                commands_emitted=commands_emitted,
                                dispatches=dispatches,
                                failures=failures,
                                started_at_ms=started_at_ms,
                                now_ms=feature_frame.timestamp_ms,
                            ),
                        )
        except KeyboardInterrupt:
            pass
        finally:
            capture.release()
            if preview_renderer is not None:
                preview_renderer.close()

        summary = self.logger.summary()
        if self.log_path is not None:
            self.log_writer(self.log_path, _entries_to_jsonl(self.logger))

        return LiveRunResult(
            success=frames_read > 0 and failures == 0 and terminal_error_code is None,
            frames_read=frames_read,
            hand_frames=hand_frames,
            commands_emitted=commands_emitted,
            dispatches=dispatches,
            failures=failures,
            read_failures=read_failures,
            backend=controller.backend_name,
            log_records=summary.total_records,
            preview_frames=preview_frames,
            average_latency_ms=summary.average_latency_ms,
            p95_latency_ms=summary.p95_latency_ms,
            log_path=self.log_path,
            error_code=terminal_error_code,
        )

    def _create_default_perception(
        self,
        image_width: int,
        image_height: int,
    ) -> MediaPipeHandPerception:
        model_asset_path = self.model_asset_path or environ.get("TOUCHLESS_HAND_LANDMARKER_MODEL")
        return MediaPipeHandPerception(
            detector_factory=create_mediapipe_detector_factory(
                model_asset_path=model_asset_path,
            ),
            image_width=image_width,
            image_height=image_height,
        )

    def _create_controller(self) -> MouseController:
        if self.dry_run:
            return _NoopMouseController()
        return self.controller_factory()

    def _create_preview_renderer(self) -> PreviewRenderer | None:
        if not self.preview:
            return None
        return self.preview_renderer or OpenCVPreviewRenderer(
            preview_width=self.preview_width,
            preview_height=self.preview_height,
        )

    def _configure_capture(self, capture: object) -> None:
        setter = getattr(capture, "set", None)
        if setter is None:
            return
        for property_id, value in (
            (_opencv_property("CAP_PROP_FRAME_WIDTH", 3), self.image_width),
            (_opencv_property("CAP_PROP_FRAME_HEIGHT", 4), self.image_height),
            (_opencv_property("CAP_PROP_FPS", 5), self.camera_fps),
            (_opencv_property("CAP_PROP_BUFFERSIZE", 38), self.camera_buffer_size),
        ):
            setter(property_id, value)

    def _poll_latest_hand(self, perception: Any) -> object | None:
        elapsed_ms = 0
        while True:
            hand_frame = perception.poll_latest()
            if hand_frame is not None or elapsed_ms >= self.poll_timeout_ms:
                return hand_frame
            self.sleep_ms(self.poll_interval_ms)
            elapsed_ms += self.poll_interval_ms


@dataclass(slots=True)
class _NoopMouseController:
    backend_name: str = "dry_run"

    def dispatch(self, command: ActionCommand) -> OSDispatchResult:
        return OSDispatchResult(
            timestamp_ms=command.timestamp_ms,
            command_type=command.type,
            success=True,
            backend=self.backend_name,
            error_code=None,
            dispatch_latency_ms=0.0,
        )


@contextlib.contextmanager
def _native_log_sink(enabled: bool):
    if not enabled:
        yield
        return

    stderr_fd = 2
    saved_stderr_fd = os.dup(stderr_fd)
    try:
        with open(os.devnull, "w", encoding="utf-8") as sink:
            os.dup2(sink.fileno(), stderr_fd)
            yield
    finally:
        os.dup2(saved_stderr_fd, stderr_fd)
        os.close(saved_stderr_fd)


def _entries_to_jsonl(logger: SessionLogger) -> str:
    lines = [json.dumps(asdict(entry), sort_keys=True) for entry in logger.entries]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _create_pipeline(
    *,
    preset_name: str,
    invert_x: bool,
    invert_y: bool,
    gain_scale: float,
) -> TouchlessPipeline:
    preset = SensitivityPreset.named(preset_name)
    return TouchlessPipeline(
        detector=PrimitiveDetector(preset=preset),
        machine=InteractionStateMachine(preset=preset),
        mapper=CursorMapper(
            preset=preset,
            invert_x=invert_x,
            invert_y=invert_y,
            gain_scale=gain_scale,
        ),
    )


def _opencv_property(name: str, fallback: int) -> int:
    try:
        import cv2
    except ImportError:
        return fallback
    return int(getattr(cv2, name, fallback))


def _pipeline_state(pipeline: object, commands: Sequence[ActionCommand]) -> str:
    state = getattr(pipeline, "state", None)
    if isinstance(state, str):
        return state
    if commands:
        return commands[-1].source_state
    return "Pointing"


def _preview_stats(
    *,
    frames_read: int,
    hand_frames: int,
    commands_emitted: int,
    dispatches: int,
    failures: int,
    started_at_ms: int | None,
    now_ms: int,
) -> PreviewStats:
    elapsed_ms = max(1, now_ms - (started_at_ms or now_ms))
    return PreviewStats(
        frames_read=frames_read,
        hand_frames=hand_frames,
        commands_emitted=commands_emitted,
        dispatches=dispatches,
        failures=failures,
        fps=(frames_read * 1000.0) / elapsed_ms,
    )
