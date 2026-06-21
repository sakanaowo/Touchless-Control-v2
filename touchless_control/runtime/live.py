from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, dataclass, field
from os import environ
from typing import Any, Callable, Protocol, Sequence

from touchless_control.control.os.base import MouseController
from touchless_control.control.os.factory import create_mouse_controller
from touchless_control.core.contracts import ActionCommand, OSDispatchResult
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
    suppress_native_logs: bool = True
    capture_factory: CaptureFactory = _default_capture_factory
    perception_factory: PerceptionFactory | None = None
    frame_converter: FrameConverter = _default_frame_converter
    timestamp_ms: TimestampClock = _now_ms
    poll_timeout_ms: int = 20
    poll_interval_ms: int = 2
    sleep_ms: SleepFn = _sleep_ms
    normalizer: FeatureNormalizer = field(default_factory=FeatureNormalizer)
    pipeline: TouchlessPipeline = field(default_factory=TouchlessPipeline)
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
                backend="dry_run" if self.dry_run else "",
                log_path=self.log_path,
                error_code="camera_open_failed",
            )

        frames_read = 0
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
        try:
            perception_factory = self.perception_factory or self._create_default_perception
            with _native_log_sink(self.suppress_native_logs):
                perception = perception_factory(self.image_width, self.image_height)
                while (frame_limit is None or frames_read < frame_limit) and not stop_requested:
                    ok, frame = capture.read()
                    if not ok:
                        break

                    timestamp_ms = self.timestamp_ms()
                    if started_at_ms is None:
                        started_at_ms = timestamp_ms
                    frames_read += 1
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

                    hand_frames += 1
                    feature_frame = self.normalizer.to_features(hand_frame)
                    commands = self.pipeline.step(feature_frame)
                    commands_emitted += len(commands)
                    results = self.pipeline.flush(controller)
                    dispatches += len(results)
                    failures += sum(1 for result in results if not result.success)
                    latency_ms = float(max(0, self.timestamp_ms() - feature_frame.timestamp_ms))
                    self.logger.record(
                        feature_frame=feature_frame,
                        primitive_events=tuple(
                            getattr(self.pipeline, "last_primitive_events", ())
                        ),
                        interaction_events=tuple(
                            getattr(self.pipeline, "last_interaction_events", ())
                        ),
                        commands=commands,
                        results=results,
                        latency_ms=latency_ms,
                    )
                    if preview_renderer is not None:
                        snapshot = self.overlay.snapshot(
                            feature_frame=feature_frame,
                            state=_pipeline_state(self.pipeline, commands),
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
            success=frames_read > 0 and failures == 0,
            frames_read=frames_read,
            hand_frames=hand_frames,
            commands_emitted=commands_emitted,
            dispatches=dispatches,
            failures=failures,
            backend=controller.backend_name,
            log_records=summary.total_records,
            preview_frames=preview_frames,
            average_latency_ms=summary.average_latency_ms,
            p95_latency_ms=summary.p95_latency_ms,
            log_path=self.log_path,
            error_code=None if frames_read > 0 else "camera_read_failed",
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
        return self.preview_renderer or OpenCVPreviewRenderer()

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
