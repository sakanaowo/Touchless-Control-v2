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
- Camera snapshot command: `uv run python main.py camera-snapshot --camera-index 0 --output C:\tmp\touchless-frame.jpg`.
- Live observable dry-run command: `uv run python main.py live --dry-run --preview --frames 300 --camera-index 0 --model C:\tmp\hand_landmarker.task --log C:\tmp\touchless-session.jsonl`.
- Live OS-dispatch command: `uv run python main.py live --frames 300 --camera-index 0 --model C:\tmp\hand_landmarker.task`.
- Add `--verbose-mediapipe` only when debugging native MediaPipe logs; live mode suppresses native stderr noise by default.
- Verification command for the current implementation slice: `uv run python -m unittest discover`.
- AI docs validation command: `npx ai-devkit@latest lint --feature touchless-control-mvp`.

## Code Structure
Current package layout:
- `touchless_control/__init__.py`: public package exports.
- `touchless_control/core/contracts.py`: immutable contracts for hand, face/attention intent context, primitives, interactions, actions, and OS dispatch.
- `touchless_control/core/config.py`: MVP sensitivity presets and initial calibration profile/service.
- `touchless_control/vision/camera.py`: OpenCV camera smoke runner and snapshot runner for MediaPipe startup and camera-source validation.
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
- `touchless_control/runtime/pipeline.py`: multimodal-ready runtime pipeline that connects intent context, primitives, state machine, cursor mapping, and action queue, while retaining the latest primitive and interaction events for live logging.
- `touchless_control/runtime/live.py`: live camera runtime runner that connects camera capture, MediaPipe perception, feature normalization, pipeline stepping, queue flushing, dry-run or OS dispatch, and optional JSONL session logging.
- `touchless_control/presentation/overlay.py`: overlay snapshot presenter for state, tracking status, active mode, and latency warning data.
- `touchless_control/presentation/preview.py`: OpenCV preview renderer that displays camera frames with hand landmarks, pinch line/center, action badge, live counters/FPS, runtime state, tracking, command, backend, and latency data for human validation.
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
- `tests/test_main_cli.py`: `camera-smoke` and `live` CLI tests.
- `tests/test_live_runner.py`: live runner loop, dry-run controller, and dispatch integration tests.
- `tests/test_action_queue.py`: queue coalescing, button ordering, safe release, and flush tests.
- `tests/test_overlay.py`: overlay snapshot state, mode, tracking-status, and latency-warning tests.
- `tests/test_preview.py`: OpenCV preview renderer text/landmark drawing tests using a fake `cv2` module.
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
- When a `hand_landmarker.task` model path is provided through `--model` or `TOUCHLESS_HAND_LANDMARKER_MODEL`, the MediaPipe factory now prefers the current MediaPipe Tasks API even if the legacy `mediapipe.solutions` package is also present.
- The legacy `mediapipe.solutions.hands` path remains only as a no-model fallback.
- Added `CameraSmokeRunner` and `camera-smoke` CLI for OpenCV camera startup and MediaPipe detector smoke tests.
- Added `CameraSnapshotRunner` and `camera-snapshot` CLI for saving a real camera frame when hand detection returns zero frames.
- Camera smoke waits briefly for async MediaPipe callbacks after each submitted frame so hand detections are not missed by immediate polling.
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
- Added `LiveRunner` and `live` CLI command for human MVP testing.
- `live --dry-run` runs the full camera/perception/feature/pipeline loop but dispatches through a no-op controller.
- `live --preview` opens an OpenCV preview window that overlays observable state, tracking status, pinch/stability metrics, emitted commands, backend, and latency on the camera feed.
- `live` without `--dry-run` uses OS auto-detection and Windows `SendInput` on Windows.
- Live CLI output includes `mode=dry_run|dispatch` and backend name, for example `backend=dry_run` or `backend=windows_sendinput`.
- Live CLI output includes `preview_frames` so manual testers can verify frames were rendered to the observable preview path.
- Live CLI accepts `--log <path>` to write one JSONL session record per processed hand frame, and output reports `log_records` plus `p95_latency_ms`.
- Live JSONL records now include latest primitive types and interaction transition reasons from the runtime pipeline.
- Live preview passes the current `HandFrame` to the renderer so MediaPipe landmarks are drawn over the camera frame.
- Live preview now displays live FPS/counters, highlights emitted commands with an action badge, and draws the thumb-index pinch line plus pinch center for threshold debugging.
- Live mode suppresses noisy native MediaPipe stderr logs by default and exposes `--verbose-mediapipe` for debugging.
- Live runs flush queued commands every processed hand frame so cursor actions do not accumulate behind camera processing.
- Live mode waits briefly for async MediaPipe callbacks after frame submission before deciding that no hand frame is available.

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
- Runtime pipeline remains IO-free; `LiveRunner` owns camera IO and OS dispatch wiring.
- Human testing should use `live --dry-run --preview --log <path>` first, then remove `--dry-run` only after preview and logs show stable hand frames, state transitions, and command emission.
- Future face-recognition and face-attention models should plug into `IntentContext` and avoid coupling directly to `PrimitiveDetector` or `InteractionStateMachine`.
- Refactored package layout by responsibility so future face and attention models can be added under `vision/face` and `vision/attention` without growing the hand modules.
- Split hand interaction into `interaction/primitives.py` and `interaction/state_machine.py`.
- Split control into cursor mapping, queueing, and OS backend modules.
- Added compatibility wrappers so existing tests and public imports keep working while new code can use the scaled package paths.

## Integration Points
- OS controller auto-detection is implemented through `create_mouse_controller()`.
- Windows auto-detection now wires a real `SendInput` sender when no sender is injected.
- Linux auto-detection still requires an injected writer until the real `/dev/uinput` writer is implemented.
- Live runtime is implemented through `LiveRunner` and `main.py live`.
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
- Live runtime red step: `uv run python -m unittest tests.test_main_cli tests.test_live_runner` failed with 3 expected missing `touchless_control.runtime.live` errors.
- Live runtime green step: `uv run python -m unittest tests.test_main_cli tests.test_live_runner` passed with 5 tests after adding `LiveRunner`, `LiveRunResult`, dry-run controller dispatch, and `main.py live`.
- MediaPipe Tasks preference red step: `uv run python -m unittest tests.test_perception tests.test_live_runner tests.test_main_cli` failed when `--model` still fell through to the legacy `solutions` path and live results lacked backend reporting.
- MediaPipe Tasks preference green step: `uv run python -m unittest tests.test_perception tests.test_live_runner tests.test_main_cli` passed with 10 tests after preferring Tasks API for model-backed runs and adding live mode/backend output.
- Live log suppression red step: `uv run python -m unittest tests.test_main_cli` failed because `--verbose-mediapipe` was unsupported and live did not pass log-suppression configuration.
- Live log suppression green step: `uv run python -m unittest tests.test_main_cli` passed with 4 tests after adding default native log suppression and `--verbose-mediapipe`.
- Async perception red step: `uv run python -m unittest tests.test_camera tests.test_live_runner` failed with missing `poll_timeout_ms` support for delayed MediaPipe callbacks.
- Async perception green step: `uv run python -m unittest tests.test_camera tests.test_live_runner` passed with 6 tests after adding bounded poll-wait behavior to camera smoke and live runtime.
- Camera snapshot red step: `uv run python -m unittest tests.test_camera tests.test_main_cli` failed with expected missing `CameraSnapshotRunner`/`CameraSnapshotResult` imports.
- Camera snapshot green step: `uv run python -m unittest tests.test_camera tests.test_main_cli` passed with 10 tests after adding `camera-snapshot`.
- Local camera snapshot verification: `uv run python main.py camera-snapshot --camera-index 0 --output C:\tmp\touchless-frame.jpg` exited 0 with `success=True frames_read=1 error_code=None`.
- Local live dry-run verification after async poll-wait: `uv run python main.py live --dry-run --frames 60 --camera-index 0 --model C:\tmp\hand_landmarker.task` exited 0 with `success=True mode=dry_run backend=dry_run frames_read=60 hand_frames=60 commands=0 dispatches=0 failures=0 error_code=None`.
- Live session logging red step: `uv run python -m unittest tests.test_live_runner` failed with expected missing `log_records`/`log_path` support.
- Live session logging green step: `uv run python -m unittest tests.test_live_runner` passed with 4 tests after adding per-hand-frame `SessionLogger` records, JSONL log writing, and latency summary fields.
- Live CLI logging red step: `uv run python -m unittest tests.test_main_cli` failed because `--log` was unsupported.
- Live CLI logging green step: `uv run python -m unittest tests.test_main_cli tests.test_live_runner` passed with 9 tests after adding `--log`, `log_records`, `p95_latency_ms`, and `log_path` reporting.
- Live preview red step: `uv run python -m unittest tests.test_live_runner tests.test_main_cli` failed because `LiveRunner` did not support `preview` and CLI rejected `--preview`.
- Live preview green step: `uv run python -m unittest tests.test_main_cli tests.test_live_runner` passed with 11 tests after adding `OpenCVPreviewRenderer`, preview renderer injection, `--preview`, and `preview_frames` reporting.
- Live observability red step: `uv run python -m unittest tests.test_live_runner tests.test_preview` failed because live JSONL omitted primitive/reason data and preview renderer did not accept `hand_frame`.
- Live observability green step: `uv run python -m unittest tests.test_live_runner tests.test_preview` passed with 7 tests after retaining pipeline primitive/interaction events, logging them from `LiveRunner`, passing `HandFrame` to preview, and drawing landmarks.
- Preview diagnostics red step: `uv run python -m unittest tests.test_preview tests.test_live_runner` failed because `PreviewStats` did not exist and `LiveRunner` did not pass stats to preview.
- Preview diagnostics green step: `uv run python -m unittest tests.test_preview tests.test_live_runner` passed with 8 tests after adding `PreviewStats`, live FPS/counters, action badge, and pinch line/center rendering.
