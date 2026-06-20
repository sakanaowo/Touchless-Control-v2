---
phase: implementation
title: Touchless Control MVP Implementation Guide
description: Implementation notes, changed files, and code guidelines for the touchless mouse-control MVP
---

# Touchless Control MVP Implementation Guide

## Development Setup
- Use the feature worktree at `C:/Code/Touchless-Control-v2/.worktrees/feature-touchless-control-mvp`.
- Python is run through `uv` in this environment because `python` and `py` are not directly available on PATH.
- Camera/MediaPipe runtime uses Python 3.12 because MediaPipe is not usable with the previous Python 3.14 project setting.
- Camera smoke command: `uv run python main.py camera-smoke --frames 30 --camera-index 0 --model C:\tmp\hand_landmarker.task`.
- Verification command for the current implementation slice: `uv run python -m unittest discover`.
- AI docs validation command: `npx ai-devkit@latest lint --feature touchless-control-mvp`.

## Code Structure
Current package layout:
- `touchless_control/__init__.py`: public package exports.
- `touchless_control/core/contracts.py`: immutable contracts for hand, face/attention intent context, primitives, interactions, actions, and OS dispatch.
- `touchless_control/core/config.py`: MVP sensitivity presets and initial calibration profile/service.
- `touchless_control/vision/camera.py`: OpenCV camera smoke runner for MediaPipe startup validation.
- `touchless_control/vision/hands/mediapipe.py`: injectable MediaPipe hand perception adapter and one-hand live-stream config.
- `touchless_control/vision/hands/features.py`: hand feature extraction from `HandFrame` to `FeatureFrame`.
- `touchless_control/vision/face/`: reserved package for future face-recognition model integration.
- `touchless_control/vision/attention/`: reserved package for future face-attention/gaze model integration.
- `touchless_control/intent/policy.py`: multimodal intent policy helpers, including attention gating.
- `touchless_control/interaction/primitives.py`: primitive detector with pinch hysteresis and scroll disambiguation.
- `touchless_control/interaction/state_machine.py`: hand interaction state machine and safety policy.
- `touchless_control/control/cursor.py`: relative cursor mapper.
- `touchless_control/control/queue.py`: bounded action queue and safe release tracking.
- `touchless_control/control/os/factory.py`: OS auto-detection for mouse-controller selection.
- `touchless_control/control/os/windows.py`: Windows mouse-controller payload adapter and `SendInput` sender.
- `touchless_control/control/os/linux.py`: Linux/uinput-style mouse-controller payload adapter.
- `touchless_control/runtime/pipeline.py`: multimodal-ready runtime pipeline that connects intent context, primitives, state machine, cursor mapping, and action queue.
- `touchless_control/presentation/overlay.py`: overlay snapshot presenter for state, tracking status, active mode, and latency warning data.
- `touchless_control/observability/logger.py`: structured session log entries and summary metrics.
- `touchless_control/observability/acceptance.py`: automated acceptance summary checks and threshold tuning helpers.
- Compatibility wrappers remain at `touchless_control.contracts`, `config`, `camera`, `perception`, `features`, `interaction`, `control`, `runtime`, `presentation`, `observability`, and `acceptance`.
- `tests/test_contracts.py`: contract import, immutability, and baseline config tests.
- `tests/test_acceptance.py`: automated acceptance checks and threshold tuning tests.
- `tests/test_calibration.py`: sensitivity preset selection and initial calibration tests.
- `tests/test_camera.py`: camera smoke runner success/failure tests with fake capture and perception.
- `tests/test_features.py`: feature normalization, pinch ratio, and tracking-loss tests.
- `tests/test_landmark_fixtures.py`: landmark fixture tests.
- `tests/test_perception.py`: perception adapter configuration, async submit, callback conversion, and empty-result tests.
- `tests/test_primitives.py`: pointing, pinch hysteresis, open palm, two-finger swipe, and tracking-loss primitive tests.
- `tests/test_state_machine.py`: state transition, click, drag, tracking-loss safe release, and scrolling tests.
- `tests/test_interaction_flows.py`: cross-component click, drag, scroll, tracking-loss, and paused-flow integration tests.
- `tests/test_cursor_mapping.py`: deadzone, relative movement, and max-step clamp tests.
- `tests/test_mouse_controller.py`: Windows/Linux controller payload mapping and dispatch-error tests.
- `tests/test_main_cli.py`: `camera-smoke` CLI tests.
- `tests/test_action_queue.py`: queue coalescing, button ordering, safe release, and flush tests.
- `tests/test_overlay.py`: overlay snapshot state, mode, tracking-status, and latency-warning tests.
- `tests/test_observability.py`: session log record and summary metric tests.
- `tests/test_runtime_pipeline.py`: runtime movement dispatch and paused-state gating tests.
- `tests/test_package_layout.py`: scaled package-path import tests and legacy import compatibility tests.
- `tests/fixtures/landmarks.py`: reusable hand landmark fixtures.

Planned package boundaries remain:
- `perception`: camera and MediaPipe integration.
- `features`: normalization and feature extraction.
- `interaction`: primitive detection, state machine, safety policy.
- `control`: action mapping, queue, and OS backends.
- `presentation`: overlay and status feedback.
- `observability`: logs and metrics.
- `config`: presets and calibration persistence.

## Implementation Notes
### Completed Foundation Tasks
- Removed obsolete `alea-aircursor` and `Virtual-Mouse-using-OpenCV` reference repositories from the feature branch.
- Added `.worktrees/` to `.gitignore`.
- Added immutable dataclasses for:
  - `HandFrame`
  - `FeatureFrame`
  - `FaceFrame`
  - `AttentionFrame`
  - `IntentSignal`
  - `IntentContext`
  - `PrimitiveEvent`
  - `InteractionEvent`
  - `ActionCommand`
  - `OSDispatchResult`
- Added `SensitivityPreset.balanced()` using the requirements baseline values.
- Added named sensitivity presets: `gentle`, `balanced`, and `responsive`.
- Added `CalibrationProfile` and `CalibrationService` to derive palm-scale baseline, jitter, pinch thresholds, and click/drag motion guards from feature samples.
- Added landmark fixtures for stable pointing and tracking-loss scenarios.

### Completed Core Interaction Tasks
- Implemented `MediaPipeHandPerception` with `MediaPipeHandConfig`.
- `MediaPipeHandConfig` defaults to `num_hands = 1`, `running_mode = "LIVE_STREAM"`, and 0.5 confidence thresholds.
- The adapter accepts an injected detector factory so unit tests do not require the real MediaPipe runtime.
- The adapter converts MediaPipe-like callback results into immutable `HandFrame` values and keeps only the latest valid frame.
- Added `create_mediapipe_detector_factory()` for real MediaPipe startup.
- The MediaPipe factory supports the legacy `mediapipe.solutions.hands` path when available and the current MediaPipe Tasks API when only `mediapipe.tasks` is available.
- MediaPipe Tasks requires a `hand_landmarker.task` model path through `--model` or `TOUCHLESS_HAND_LANDMARKER_MODEL`.
- Added `CameraSmokeRunner` and `camera-smoke` CLI for OpenCV camera startup and MediaPipe detector smoke tests.
- Added `create_mouse_controller()` to auto-select Windows or Linux controller by operating system name.
- Implemented `FeatureNormalizer` for palm scale, palm center, canonical landmark points, index direction, hand velocity, pinch ratio, finger count, two-finger readiness, open-palm signal, and tracking-loss flag.
- Tracking stability currently uses the minimum of detection, presence, and tracking confidence as the safety-first score.
- Implemented `PrimitiveDetector` for `pointing`, `pinch_closed`, `pinch_opened`, `open_palm`, `two_finger_swipe`, and `tracking_lost`.
- `PrimitiveDetector` keeps internal pinch state so close/open hysteresis prevents flicker between threshold boundaries.
- Tracking loss suppresses all other primitive events and resets pinch state.
- Implemented `InteractionStateMachine` for `NoHand`, `Pointing`, `ClickCandidate`, `ClickCommitted`, `Dragging`, `Scrolling`, `Paused`, `TrackingLost`, and `Cooldown`.
- Click commits only on valid short pinch release and emits `left_click` from `ClickCommitted`.
- Held pinch enters `Dragging` and emits `left_down`; tracking loss during drag emits safe `left_up`.
- Two-finger swipe enters dedicated `Scrolling` and emits `scroll_vertical`.
- Implemented `CursorMapper` for relative movement only.
- Cursor mapping returns a `none` action inside deadzone, applies adaptive EMA smoothing, computes acceleration gain, and clamps per-frame movement to `max_step_px`.
- Implemented `MouseController` protocol with `WindowsMouseController` and `LinuxMouseController`.
- Windows/Linux controllers use injected sender/writer callables so unit tests never inject real OS input.
- Windows controller maps actions to move/button/wheel payloads and can now create a real `SendInput` sender when no test sender is injected.
- Linux controller maps actions to uinput-style `EV_REL` and `EV_KEY` payloads; the real `/dev/uinput` writer remains a follow-up.
- Dispatch failures are captured as `OSDispatchResult(success=False, error_code=<exception type>)`.
- Implemented `ActionQueue` with bounded storage, stale movement coalescing, controller flush, and safe left-button release tracking.
- Implemented `OverlayPresenter` and immutable `OverlaySnapshot`.
- Overlay snapshots expose current state, active mode, tracking status, latency, high-latency warning flag, stability score, and pinch ratio.
- Latency warning defaults to the MVP p95 budget of 80 ms.
- Implemented `SessionLogger`, immutable `SessionLogEntry`, and immutable `SessionSummary`.
- Session log entries capture timestamp, state, primitive types, transition reasons, action types, dispatch outcomes, latency, and key feature values.
- Summary metrics currently include record count, action count, dispatch count, failure count, tracking-loss count, average latency, and nearest-rank p95 latency.
- Calibration keeps thresholds inside safe bounds and can produce a calibrated preset without mutating the source preset.
- Implemented `AcceptanceEvaluator` with p95 latency and dispatch-failure checks over `SessionSummary`.
- Implemented threshold tuning helper that makes pinch/click stricter after false clicks and makes drag harder to trigger after false drags.
- Added primitive safety coverage so pinch/drag intent suppresses ambiguous two-finger scroll primitives.
- Added scroll rate limiting using `SensitivityPreset.scroll_interval_ms`.
- Added `TouchlessPipeline` to gate cursor movement by interaction state and prevent movement dispatch while paused.
- Refactored `TouchlessPipeline.step()` into a hand-only wrapper around `TouchlessPipeline.step_context(IntentContext)`.
- Added future-facing face and attention contracts without adding a face model dependency.
- Added attention gating at the runtime boundary: when `AttentionFrame.attention_on_screen` is false, movement/click/scroll dispatch is blocked; active drag emits a safe `left_up`.
- Attention-based drag release now moves the interaction state to `Cooldown` immediately so a later attention recovery cannot emit a duplicate `left_up`.

### Patterns & Best Practices
- Contracts are frozen dataclasses with slots so state-machine inputs remain immutable per frame.
- `PrimitiveEvent.source_features` is copied into a read-only mapping to prevent downstream mutation.
- `ActionCommand.move_relative()` is the first command factory and intentionally emits relative deltas only.
- Fixtures use 21 landmarks to match MediaPipe Hands output.
- Perception runtime uses dependency injection at the detector boundary; real MediaPipe construction is now available without changing downstream contracts.
- Feature normalization treats MediaPipe image landmarks as normalized coordinates and uses wrist-to-middle-MCP distance as palm scale.
- Primitive detection remains OS-dispatch free; it emits `PrimitiveEvent` only.
- State machine emits `InteractionEvent` and `ActionCommand` only; OS dispatch remains outside this layer.
- Cursor mapping emits `ActionCommand` only; OS dispatch remains outside this layer.
- Controller unit tests use injected callables only; auto-detection selects the Windows/Linux controller, and Windows can use a real `SendInput` sender by default.
- Action queue is the integration boundary between state-machine/cursor-mapper outputs and OS controller dispatch.
- Overlay presentation is a data-only boundary; a future GUI renderer can consume `OverlaySnapshot` without coupling to interaction internals.
- Session logging is currently in memory and IO-free; a JSONL/file sink can be added later without changing the pipeline-facing record API.
- Acceptance automation consumes session summaries; real camera and OS acceptance still requires manual/hardware execution.
- Runtime pipeline remains IO-free; real camera capture and real OS injection stay outside automated tests.
- Future face-recognition and face-attention models should plug into `IntentContext` and avoid coupling directly to `PrimitiveDetector` or `InteractionStateMachine`.
- Refactored package layout by responsibility so future face and attention models can be added under `vision/face` and `vision/attention` without growing the hand modules.
- Split hand interaction into `interaction/primitives.py` and `interaction/state_machine.py`.
- Split control into cursor mapping, queueing, and OS backend modules.
- Added compatibility wrappers so existing tests and public imports keep working while new code can use the scaled package paths.

## Integration Points
- OS controller auto-detection is implemented through `create_mouse_controller()`.
- Windows auto-detection now wires a real `SendInput` sender when no sender is injected.
- Linux auto-detection still requires an injected writer until the real `/dev/uinput` writer is implemented.
- The perception adapter is implemented as a testable boundary around a MediaPipe-like async detector.
- Real MediaPipe detector construction is implemented. For MediaPipe Tasks, pass a `hand_landmarker.task` model path.
- The current code provides the contracts, perception boundary, feature normalization, state machine, OS backend abstraction, Windows `SendInput` sender, and fixtures required for the automated MVP foundation.

## Error Handling
- OS/backend errors are captured by mouse controllers and returned as `OSDispatchResult(success=False, error_code=<exception type>)`.
- Windows `SendInput` partial/failed sends raise `OSError`, which is converted into a dispatch failure by `WindowsMouseController`.

## Performance Considerations
- The contract layer is immutable and lightweight.
- Future queue and perception work must preserve the design decision to prefer latest-frame freshness over stale backlogs.

## Security Notes
- Windows input injection uses the isolated `SendInput` sender behind the controller boundary.
- Future Linux backend work must isolate `/dev/uinput` permissions and report failures through `OSDispatchResult`.

## Verification Evidence
- Red step: `uv run python -m unittest discover` failed with 5 expected import errors before production code existed.
- Green step: `uv run python -m unittest discover` passed with 5 tests.
- Task 2.1 red step: `uv run python -m unittest discover` failed with 3 expected `touchless_control.perception` import errors.
- Task 2.1 green step: `uv run python -m unittest discover` passed with 8 tests.
- Task 2.2 red step: `uv run python -m unittest discover` failed with 3 expected `touchless_control.features` import errors.
- Task 2.2 green step: `uv run python -m unittest discover` passed with 11 tests.
- Task 2.3 red step: `uv run python -m unittest discover` failed with 5 expected `touchless_control.interaction` import errors.
- Task 2.3 green step: `uv run python -m unittest discover` passed with 16 tests.
- Task 2.4 red step: `uv run python -m unittest discover` failed with 5 expected `InteractionStateMachine` import errors.
- Task 2.4 green step: `uv run python -m unittest discover` passed with 21 tests.
- Task 2.5 red step: `uv run python -m unittest discover` failed with 3 expected `touchless_control.control` import errors.
- Task 2.5 green step: `uv run python -m unittest discover` passed with 24 tests.
- Task 3.1 red step: `uv run python -m unittest discover` failed with 4 expected missing `WindowsMouseController`/`LinuxMouseController` import errors.
- Task 3.1 green step: `uv run python -m unittest discover` passed with 28 tests.
- Task 3.2 red step: `uv run python -m unittest discover` failed with 4 expected missing `ActionQueue` import errors.
- Task 3.2 green step: `uv run python -m unittest discover` passed with 32 tests.
- Task 3.3 red step: `uv run python -m unittest discover` failed with 3 expected missing `touchless_control.presentation` import errors.
- Task 3.3 green step: `uv run python -m unittest discover` passed with 35 tests.
- Task 3.4 red step: `uv run python -m unittest discover` failed with 2 expected missing `touchless_control.observability` import errors.
- Task 3.4 green step: `uv run python -m unittest discover` passed with 37 tests.
- Task 3.5 red step: `uv run python -m unittest discover` failed with 2 expected missing preset/calibration API errors.
- Task 3.5 green step: `uv run python -m unittest discover` passed with 39 tests.
- Task 3.6 red step: `uv run python -m unittest discover` failed with 3 expected missing `touchless_control.acceptance` import errors.
- Task 3.6 green step: `uv run python -m unittest discover` passed with 42 tests.
- Testing phase red step: `uv run python -m unittest discover` failed when ambiguous pinch/scroll emitted both `pinch_closed` and `two_finger_swipe`.
- Testing phase green step: `uv run python -m unittest discover` passed with 48 tests after suppressing scroll while pinch is closed.
- Testing phase red step: `uv run python -m unittest discover` failed when repeated scroll wheel commands ignored `scroll_interval_ms`.
- Testing phase green step: `uv run python -m unittest discover` passed with 49 tests after adding scroll interval gating.
- Testing phase red step: `uv run python -m unittest discover` failed with 2 expected missing `touchless_control.runtime` import errors.
- Testing phase green step: `uv run python -m unittest discover` passed with 51 tests after adding `TouchlessPipeline`.
- OS auto-detect red step: `uv run python -m unittest discover` failed with 3 expected missing `create_mouse_controller` import errors.
- OS auto-detect green step: `uv run python -m unittest discover` passed with 54 tests.
- Camera runner red step: `uv run python -m unittest discover` failed with 2 expected missing `touchless_control.camera` import errors.
- MediaPipe factory/camera green step: `uv run python -m unittest discover` passed with 59 tests.
- Dependency verification: `uv run python -c "import cv2; print('cv2 ok', cv2.__version__)"` passed with OpenCV 4.13.0.
- Dependency verification: `uv run python -c "import mediapipe as mp; print('mediapipe ok', mp.__version__)"` passed with MediaPipe 0.10.35.
- Camera smoke verification: `uv run python main.py camera-smoke --frames 30 --camera-index 0 --model C:\tmp\hand_landmarker.task` exited 0 with `success=True frames_read=30 hand_frames=0 error_code=None`.
- Multimodal refactor red step: `uv run python -m unittest discover` failed with 5 expected missing `AttentionFrame`/`IntentContext` import errors.
- Multimodal refactor green step: `uv run python -m unittest discover` passed with 63 tests after adding `FaceFrame`, `AttentionFrame`, `IntentSignal`, `IntentContext`, and `TouchlessPipeline.step_context()`.
- Package-layout refactor verification: `uv run python -m unittest discover` passed with 65 tests after moving implementation into `core`, `vision`, `intent`, `interaction`, `control`, `runtime`, `presentation`, and `observability` packages.
- Windows `SendInput` red step: `uv run python -m unittest discover` failed with 3 expected errors for missing default Windows sender behavior and missing `create_sendinput_sender`.
- Windows `SendInput` green step: `uv run python -m unittest discover` passed with 68 tests after adding the real sender factory and factory default wiring.
- Review safety red step: `uv run python -m unittest tests.test_runtime_pipeline` failed when attention recovery after a drag safe-release emitted a duplicate `left_up`.
- Review safety green step: `uv run python -m unittest tests.test_runtime_pipeline` passed with 6 tests after moving the state machine to `Cooldown` on attention-based drag release.
