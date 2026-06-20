"""Core package for the Touchless Control MVP."""

from touchless_control.core.config import CalibrationProfile, CalibrationService, SensitivityPreset
from touchless_control.core.contracts import (
    ActionCommand,
    AttentionFrame,
    FaceFrame,
    FeatureFrame,
    HandFrame,
    IntentContext,
    IntentSignal,
    InteractionEvent,
    OSDispatchResult,
    PrimitiveEvent,
)
from touchless_control.control import (
    ActionQueue,
    CursorMapper,
    LinuxMouseController,
    MouseController,
    WindowsMouseController,
    create_mouse_controller,
)
from touchless_control.interaction import InteractionStateMachine, PrimitiveDetector
from touchless_control.observability import (
    AcceptanceCheck,
    AcceptanceCriteria,
    AcceptanceEvaluator,
    SessionLogger,
    SessionLogEntry,
    SessionSummary,
)
from touchless_control.presentation import OverlayPresenter, OverlaySnapshot
from touchless_control.runtime import TouchlessPipeline
from touchless_control.vision import CameraSmokeResult, CameraSmokeRunner
from touchless_control.vision.hands import (
    FeatureNormalizer,
    MediaPipeHandConfig,
    MediaPipeHandPerception,
    create_mediapipe_detector_factory,
)

__all__ = [
    "ActionCommand",
    "ActionQueue",
    "AcceptanceCheck",
    "AcceptanceCriteria",
    "AcceptanceEvaluator",
    "AttentionFrame",
    "CameraSmokeResult",
    "CameraSmokeRunner",
    "CalibrationProfile",
    "CalibrationService",
    "CursorMapper",
    "FaceFrame",
    "FeatureFrame",
    "HandFrame",
    "IntentContext",
    "IntentSignal",
    "InteractionEvent",
    "OSDispatchResult",
    "PrimitiveEvent",
    "SensitivityPreset",
    "FeatureNormalizer",
    "InteractionStateMachine",
    "PrimitiveDetector",
    "SessionLogger",
    "SessionLogEntry",
    "SessionSummary",
    "TouchlessPipeline",
    "MediaPipeHandConfig",
    "MediaPipeHandPerception",
    "create_mediapipe_detector_factory",
    "MouseController",
    "OverlayPresenter",
    "OverlaySnapshot",
    "WindowsMouseController",
    "LinuxMouseController",
    "create_mouse_controller",
]
