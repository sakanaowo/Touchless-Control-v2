from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import SimpleNamespace
from threading import Lock
from typing import Any, Callable, Protocol

from touchless_control.core.contracts import HandFrame, Point3D


class _AsyncDetector(Protocol):
    def detect_async(self, frame: Any, timestamp_ms: int) -> None:
        ...


DetectorFactory = Callable[..., _AsyncDetector]
ModuleLoader = Callable[[str], Any]


@dataclass(frozen=True, slots=True)
class MediaPipeHandConfig:
    num_hands: int = 1
    running_mode: str = "LIVE_STREAM"
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


class MediaPipeHandPerception:
    def __init__(
        self,
        *,
        detector_factory: DetectorFactory,
        image_width: int = 0,
        image_height: int = 0,
        config: MediaPipeHandConfig | None = None,
    ) -> None:
        self.config = config or MediaPipeHandConfig()
        self.image_width = image_width
        self.image_height = image_height
        self._latest: HandFrame | None = None
        self._lock = Lock()
        self._detector = detector_factory(
            config=self.config,
            result_callback=self._handle_result,
        )

    def submit(self, frame: Any, timestamp_ms: int) -> None:
        self._detector.detect_async(frame, timestamp_ms)

    def poll_latest(self) -> HandFrame | None:
        with self._lock:
            latest = self._latest
            self._latest = None
            return latest

    def _handle_result(self, result: Any, _output_image: Any, timestamp_ms: int) -> None:
        hand_landmarks = getattr(result, "hand_landmarks", None) or []
        world_landmarks = getattr(result, "hand_world_landmarks", None) or []
        handedness_values = getattr(result, "handedness", None) or []

        if not hand_landmarks or not world_landmarks or not handedness_values:
            return

        image_points = _points_from_landmarks(hand_landmarks[0])
        world_points = _points_from_landmarks(world_landmarks[0])
        if len(image_points) != 21 or len(world_points) != 21:
            return

        handedness = _first_category(handedness_values[0])
        score = float(getattr(handedness, "score", 0.0))
        frame = HandFrame(
            timestamp_ms=timestamp_ms,
            image_width=self.image_width,
            image_height=self.image_height,
            landmarks_img=image_points,
            landmarks_world=world_points,
            handedness=str(getattr(handedness, "category_name", "")).lower(),
            detection_confidence=score,
            presence_confidence=score,
            tracking_confidence=score,
        )
        with self._lock:
            self._latest = frame


def create_mediapipe_detector_factory(
    *,
    model_asset_path: str | None = None,
    module_loader: ModuleLoader = importlib.import_module,
) -> DetectorFactory:
    mediapipe = module_loader("mediapipe")
    if model_asset_path is not None:
        return _create_mediapipe_tasks_factory(
            mediapipe=mediapipe,
            model_asset_path=model_asset_path,
            module_loader=module_loader,
        )

    if not hasattr(mediapipe, "solutions"):
        raise RuntimeError(
            "MediaPipe Tasks requires a hand landmarker model path. "
            "Pass --model or set TOUCHLESS_HAND_LANDMARKER_MODEL."
        )

    def factory(*, config: MediaPipeHandConfig, result_callback: Callable[..., None]) -> _AsyncDetector:
        hands = mediapipe.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=config.num_hands,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        return _MediaPipeSolutionsDetector(
            hands=hands,
            result_callback=result_callback,
        )

    return factory


def _create_mediapipe_tasks_factory(
    *,
    mediapipe: Any,
    model_asset_path: str,
    module_loader: ModuleLoader,
) -> DetectorFactory:
    vision = module_loader("mediapipe.tasks.python.vision")
    base_options_module = module_loader("mediapipe.tasks.python.core.base_options")

    def factory(*, config: MediaPipeHandConfig, result_callback: Callable[..., None]) -> _AsyncDetector:
        options = vision.HandLandmarkerOptions(
            base_options=base_options_module.BaseOptions(model_asset_path=model_asset_path),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=config.num_hands,
            min_hand_detection_confidence=config.min_detection_confidence,
            min_hand_presence_confidence=config.min_presence_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
            result_callback=result_callback,
        )
        return _MediaPipeTasksDetector(
            mediapipe=mediapipe,
            landmarker=vision.HandLandmarker.create_from_options(options),
        )

    return factory


@dataclass(slots=True)
class _MediaPipeSolutionsDetector:
    hands: Any
    result_callback: Callable[..., None]

    def detect_async(self, frame: Any, timestamp_ms: int) -> None:
        result = self.hands.process(frame)
        adapted = SimpleNamespace(
            hand_landmarks=getattr(result, "multi_hand_landmarks", None) or [],
            hand_world_landmarks=getattr(result, "multi_hand_world_landmarks", None) or [],
            handedness=getattr(result, "multi_handedness", None) or [],
        )
        self.result_callback(adapted, frame, timestamp_ms)


@dataclass(slots=True)
class _MediaPipeTasksDetector:
    mediapipe: Any
    landmarker: Any

    def detect_async(self, frame: Any, timestamp_ms: int) -> None:
        image = self.mediapipe.Image(
            image_format=self.mediapipe.ImageFormat.SRGB,
            data=frame,
        )
        self.landmarker.detect_async(image, timestamp_ms)


def _points_from_landmarks(landmarks: Any) -> tuple[Point3D, ...]:
    return tuple(
        (
            float(getattr(landmark, "x")),
            float(getattr(landmark, "y")),
            float(getattr(landmark, "z")),
        )
        for landmark in landmarks
    )


def _first_category(categories: Any) -> Any:
    return categories[0] if isinstance(categories, list | tuple) else categories
