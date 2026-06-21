from __future__ import annotations

import time
from dataclasses import dataclass
from os import environ
from typing import Any, Callable, Protocol

from touchless_control.vision.hands.mediapipe import (
    MediaPipeHandPerception,
    create_mediapipe_detector_factory,
)


class _Capture(Protocol):
    def isOpened(self) -> bool:
        ...

    def read(self) -> tuple[bool, Any]:
        ...

    def release(self) -> None:
        ...


class _Perception(Protocol):
    def submit(self, frame: Any, timestamp_ms: int) -> None:
        ...

    def poll_latest(self) -> Any:
        ...


CaptureFactory = Callable[[int], _Capture]
PerceptionFactory = Callable[[int, int], _Perception]
FrameConverter = Callable[[Any], Any]
TimestampClock = Callable[[], int]
SleepFn = Callable[[int], None]
FrameWriter = Callable[[str, Any], bool]


def _default_capture_factory(camera_index: int) -> _Capture:
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for camera smoke tests") from error
    return cv2.VideoCapture(camera_index)


def _default_perception_factory(image_width: int, image_height: int) -> MediaPipeHandPerception:
    return MediaPipeHandPerception(
        detector_factory=create_mediapipe_detector_factory(
            model_asset_path=environ.get("TOUCHLESS_HAND_LANDMARKER_MODEL"),
        ),
        image_width=image_width,
        image_height=image_height,
    )


def _default_frame_converter(frame: Any) -> Any:
    if not hasattr(frame, "shape"):
        return frame
    try:
        import cv2
    except ImportError:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _default_frame_writer(output_path: str, frame: Any) -> bool:
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for camera snapshots") from error
    return bool(cv2.imwrite(output_path, frame))


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sleep_ms(duration_ms: int) -> None:
    time.sleep(duration_ms / 1000)


@dataclass(frozen=True, slots=True)
class CameraSmokeResult:
    success: bool
    frames_read: int
    hand_frames: int
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class CameraSnapshotResult:
    success: bool
    frames_read: int
    output_path: str
    error_code: str | None = None


@dataclass(slots=True)
class CameraSnapshotRunner:
    camera_index: int = 0
    capture_factory: CaptureFactory = _default_capture_factory
    frame_writer: FrameWriter = _default_frame_writer

    def run(self, *, output_path: str) -> CameraSnapshotResult:
        capture = self.capture_factory(self.camera_index)
        if not capture.isOpened():
            return CameraSnapshotResult(
                success=False,
                frames_read=0,
                output_path=output_path,
                error_code="camera_open_failed",
            )

        frames_read = 0
        try:
            ok, frame = capture.read()
            if not ok:
                return CameraSnapshotResult(
                    success=False,
                    frames_read=0,
                    output_path=output_path,
                    error_code="camera_read_failed",
                )
            frames_read = 1
            if not self.frame_writer(output_path, frame):
                return CameraSnapshotResult(
                    success=False,
                    frames_read=frames_read,
                    output_path=output_path,
                    error_code="snapshot_write_failed",
                )
        finally:
            capture.release()

        return CameraSnapshotResult(
            success=True,
            frames_read=frames_read,
            output_path=output_path,
        )


@dataclass(slots=True)
class CameraSmokeRunner:
    camera_index: int = 0
    image_width: int = 640
    image_height: int = 480
    model_asset_path: str | None = None
    capture_factory: CaptureFactory = _default_capture_factory
    perception_factory: PerceptionFactory | None = None
    frame_converter: FrameConverter = _default_frame_converter
    timestamp_ms: TimestampClock = _now_ms
    poll_timeout_ms: int = 20
    poll_interval_ms: int = 2
    sleep_ms: SleepFn = _sleep_ms

    def run(self, *, max_frames: int = 90) -> CameraSmokeResult:
        capture = self.capture_factory(self.camera_index)
        if not capture.isOpened():
            return CameraSmokeResult(
                success=False,
                frames_read=0,
                hand_frames=0,
                error_code="camera_open_failed",
            )

        perception_factory = self.perception_factory or self._create_default_perception
        perception = perception_factory(self.image_width, self.image_height)
        frames_read = 0
        hand_frames = 0
        try:
            for _ in range(max_frames):
                ok, frame = capture.read()
                if not ok:
                    break
                frames_read += 1
                perception.submit(self.frame_converter(frame), self.timestamp_ms())
                if self._poll_latest_hand(perception) is not None:
                    hand_frames += 1
        finally:
            capture.release()

        return CameraSmokeResult(
            success=frames_read > 0,
            frames_read=frames_read,
            hand_frames=hand_frames,
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

    def _poll_latest_hand(self, perception: _Perception) -> Any:
        elapsed_ms = 0
        while True:
            hand_frame = perception.poll_latest()
            if hand_frame is not None or elapsed_ms >= self.poll_timeout_ms:
                return hand_frame
            self.sleep_ms(self.poll_interval_ms)
            elapsed_ms += self.poll_interval_ms
