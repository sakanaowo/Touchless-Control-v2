---
phase: testing
title: Touchless Control MVP Testing Strategy
description: Acceptance and coverage plan for the touchless mouse-control MVP
---

# Touchless Control MVP Testing Strategy

## Test Coverage Goals
- Unit tests should cover all new state-machine, primitive-detection, mapping, configuration, and OS-controller abstraction logic.
- Integration tests should cover perception-to-feature contracts, state-machine-to-action contracts, and backend dispatch adapters with mocks.
- End-to-end/manual tests should measure latency, FPS, success rate, false positives, recovery, and log completeness.
- Hardware/manual validation is required for camera and real OS injection behavior.

## Unit Tests
### Contracts & Fixtures
- [x] Public package exports the core contracts.
- [x] Contract classes are dataclasses.
- [x] `ActionCommand.move_relative()` emits relative movement and remains immutable.
- [x] Balanced sensitivity preset matches the requirements baseline.
- [x] Stable pointing and tracking-loss fixtures provide 21 landmarks.
- [x] Multimodal intent contracts support optional face and attention inputs.
- [x] Intent signal source features are immutable after construction.
- [x] Scaled package paths are importable.
- [x] Legacy package paths still export the public API.

### Config & Calibration
- [x] Provides `gentle`, `balanced`, and `responsive` sensitivity presets.
- [x] Looks up named presets deterministically.
- [x] Derives palm-scale baseline, jitter, pinch thresholds, and click/drag guards from calibration samples.
- [x] Converts calibration results into a tuned preset without mutating the source preset.

### Perception Adapter
- [x] MediaPipe hand adapter uses one-hand `LIVE_STREAM` configuration.
- [x] Adapter submits frames through an async detector boundary.
- [x] Adapter converts the latest callback result into `HandFrame`.
- [x] Adapter ignores empty or incomplete landmark results.
- [x] Real MediaPipe detector factory can create a detector through MediaPipe Solutions or MediaPipe Tasks.
- [x] Real MediaPipe detector factory prefers MediaPipe Tasks API when a model path is provided, even if legacy `solutions` is also installed.

### Camera Smoke
- [x] OpenCV camera runner reads frames through an injectable capture boundary.
- [x] Camera runner waits briefly for async perception callbacks before counting a frame as no-hand.
- [x] Camera runner reports camera-open failures without crashing.
- [x] `camera-smoke` CLI reports frame and hand-frame counts.
- [x] `camera-snapshot` CLI saves one camera frame for source/lighting/framing validation.
- [x] Local smoke command opened camera index 0 and read 30 frames with MediaPipe initialized.

### Live Runtime
- [x] `live` CLI command runs a live runner and reports frame, hand-frame, command, dispatch, failure, and error counts.
- [x] `live` CLI output reports `mode` and backend so dry-run and real OS dispatch are visible.
- [x] `live` CLI accepts `--log <path>` and reports session `log_records`, `p95_latency_ms`, and `log_path`.
- [x] `live` CLI accepts `--preview` and reports `preview_frames` for observable camera/runtime validation.
- [x] `live` CLI defaults to 640x480 capture, 60 FPS request, 960x720 resizable preview, responsive sensitivity, horizontal cursor inversion, cursor gain scaling, and exposes flags for preset, axis inversion, poll timing, and camera read-failure tolerance.
- [x] `live` CLI suppresses native MediaPipe logs by default and can re-enable them with `--verbose-mediapipe`.
- [x] Live runner connects capture, perception, feature normalization, runtime pipeline, and controller dispatch through injectable boundaries.
- [x] Live runner waits briefly for async perception callbacks before counting a frame as no-hand.
- [x] Live runner processes only fresh hand-frame timestamps so stale MediaPipe live-stream outputs do not repeatedly dispatch cursor movement.
- [x] Live runner tolerates transient camera read misses before stopping and reports `read_failures`.
- [x] Live runner configures camera width, height, FPS, and buffer size through the capture boundary when supported.
- [x] Live dry-run mode avoids creating the real OS controller and dispatches through a no-op controller.
- [x] Live runner records one structured session log entry per processed hand frame and can write JSONL for manual metric regression.
- [x] Live preview renders camera frames with state, tracking status, pinch/stability metrics, commands, backend, and latency through an injectable renderer.
- [x] Live preview draws MediaPipe hand landmarks over the camera frame when a hand frame is available.
- [x] Live preview draws landmarks using actual frame dimensions so keypoints stay aligned when camera output differs from requested dimensions.
- [x] Live preview opens a resizable OpenCV window and applies initial preview dimensions.
- [x] Live preview requests keep-ratio behavior for resizable OpenCV windows when the backend supports it.
- [x] Live preview displays FPS, frame/hand/command/dispatch/failure counters, action badge, and thumb-index pinch line/center.
- [x] Live preview can stop the live loop when the tester presses the preview quit key.

### Feature Normalization
- [x] Computes palm scale consistently from landmark fixtures.
- [x] Normalizes index, thumb, middle, and palm coordinates.
- [x] Computes pinch ratio independent of hand distance to camera.
- [x] Flags tracking loss or low stability when confidence/input quality is insufficient.

### Primitive Detection
- [x] Detects `pointing`, `pinch_closed`, `pinch_opened`, `open_palm`, `two_finger_swipe`, and `tracking_lost`.
- [x] Applies close/open hysteresis and does not flicker while pinch remains between close/open thresholds.
- [x] Rejects ambiguous scroll while pinch/drag intent is active.

### Interaction State Machine
- [x] Moves `NoHand` to `Pointing` only after stable hand detection.
- [x] Commits left click only on valid pinch release before drag threshold.
- [x] Enters `Dragging` after hold threshold or early drag motion.
- [x] Sends safe release when tracking is lost during drag.
- [x] Blocks committed actions during `Paused`.
- [x] Applies `Cooldown` after click/drag completion.
- [x] Enters dedicated `Scrolling` state and dispatches bounded wheel command on two-finger swipe.

### Cursor Mapping
- [x] Applies deadzone for small hand motion.
- [x] Applies EMA/adaptive smoothing.
- [x] Applies acceleration and clamps `max_step`.
- [x] Supports configurable X/Y inversion for camera orientation fixes.
- [x] Supports configurable gain scaling for live responsiveness tuning.
- [x] Accumulates residual/subpixel movement so small intentional motion can emit cursor updates instead of being fully dropped by deadzone.
- [x] Emits relative movement, never absolute cursor targets.

### OS Controller
- [x] Converts action commands to Windows backend payloads through an injected sender.
- [x] Creates a real Windows `SendInput` sender when no test sender is injected.
- [x] Verifies the `SendInput` sender through a fake Windows API boundary.
- [x] Raises and reports failure when Windows reports a partial or failed send.
- [x] Converts action commands to Linux/uinput-style payloads through an injected writer.
- [x] Reports dispatch success, backend name, error code, and latency.
- [x] Handles backend failures without crashing the interaction loop.

### Action Queue
- [x] Ignores `none` commands.
- [x] Coalesces stale relative movement to the latest movement command.
- [x] Preserves button command order.
- [x] Enqueues safe `left_up` only when a left button is currently down.
- [x] Flushes queued commands through a controller boundary.

### Overlay Feedback
- [x] Reports current interaction state and active mode.
- [x] Reports stable, no-hand, and tracking-lost status.
- [x] Raises a latency warning when latency exceeds the 80 ms MVP budget.
- [x] Carries stability and pinch metrics needed by a renderer/debug view.

### Observability
- [x] Records timestamp, state, primitive types, transition reasons, action types, dispatch outcomes, latency, and key feature values.
- [x] Summarizes action count, dispatch count, failure count, tracking-loss count, average latency, and p95 latency.
- [x] `report --log` analyzes JSONL sessions and reports effective FPS, p95/p99 latency, action/dispatch/failure/tracking-loss counts, primitive distribution, action distribution, cursor update Hz, movement coverage, and move-gap p95.

### Acceptance Automation
- [x] Evaluates p95 latency against the 80 ms MVP budget from session summaries.
- [x] Flags dispatch failures from session summaries.
- [x] Recommends stricter pinch/click thresholds when false clicks exceed budget.
- [x] Recommends safer drag thresholds when false drags exceed budget.

## Integration Tests
- [x] `FeatureFrame` fixture -> primitive events -> click action command.
- [x] `FeatureFrame` fixture sequence -> drag down/move/up commands.
- [x] Scroll fixture sequence -> rate-limited wheel commands.
- [x] Tracking-loss sequence -> no accidental click and safe release if needed.
- [x] Paused sequence -> no click, drag, scroll, or movement dispatch.
- [x] Logger receives feature, state, action, dispatch, and latency records.
- [x] Live logger receives primitive types and interaction transition reasons from the runtime pipeline.
- [x] `IntentContext` preserves hand-only runtime behavior.
- [x] Off-screen attention blocks movement dispatch.
- [x] Off-screen attention safely releases an active drag.
- [x] Attention recovery after an active drag safe-release does not emit a duplicate `left_up`.
- [x] Live runner processes a detected hand frame, emits a pipeline command, and flushes it through the selected controller.
- [x] Live runner passes observable state and command/dispatch results to the preview renderer.
- [x] Session report CLI reads live JSONL logs and prints CLI-friendly metric lines.

## End-to-End Tests
- [ ] `TP-MOVE-STRAIGHT`: move hand left/right/up/down 20 times; p95 latency < 80 ms; no movement spike beyond `max_step`.
- [ ] `TP-MOVE-SLOW-PRECISE`: move hand slowly across a small target region; cursor update p95 gap < 50 ms; movement coverage >= 80%; no freeze > 150 ms.
- [ ] `TP-MOVE-STATIONARY`: hold pointing for 5 seconds, 10 repetitions; RMS jitter <= 6 px.
- [ ] `TP-CLICK-INTENT`: 100 short pinches; success >= 95%; p95 latency < 80 ms.
- [ ] `TP-CLICK-FALSE`: 5 minutes idle/pointing/reposition; false click <= 0.5/min.
- [ ] `TP-DRAG-INTENT`: 50 drag tasks; success >= 90%.
- [ ] `TP-DRAG-FALSE`: 100 short clicks; false drag <= 2/100.
- [ ] `TP-SCROLL-UPDOWN`: 50 up and 50 down swipes; direction correctness >= 95%; p95 latency < 80 ms.
- [ ] `TP-PAUSE-SAFETY`: random actions with open-palm interruptions; committed actions while paused = 0.
- [ ] `TP-TRACKING-LOSS`: hide hand for 1 second and return; recovery <= 2 seconds; accidental action = 0.
- [ ] `TP-LONG-SESSION`: 10-minute mixed session; effective FPS >= 30; false positives <= 1.0/min; logs complete.
- [ ] `TP-CROSS-OS`: required actions pass on Windows and Linux.

## Test Data
- Added landmark fixtures for stable pointing and tracking loss.
- Still needed: camera-derived landmark fixture sequences for jitter, pinch click, pinch drag, two-finger scroll, and open palm.
- Mock OS backends that capture commands without injecting real input.
- Fake Windows `SendInput` boundary for automated sender tests without real OS injection.
- Live dry-run no-op controller for human tests before enabling OS input.
- OpenCV preview window for observing camera framing, hand landmarks, pinch line/center, hand-tracking state, command emission, FPS/counters, backend, and latency during manual validation.
- JSONL session logs from `live --log` for manual metric regression.
- `report --log` output for manual run summaries before formal E2E acceptance sign-off.
- Automated acceptance checks over synthetic/in-memory session summaries.
- Runtime pipeline tests over synthetic `FeatureFrame` sequences.
- Multimodal intent-context tests over synthetic `AttentionFrame` values.

## Test Reporting & Coverage
- Report p50/p95/p99 latency, FPS, cursor update Hz, move-gap p50/p95/max, movement coverage, action success rate, false positives per minute, recovery time, tracking-loss rate, jitter, and log completeness.
- Current report automation covers effective FPS, p95/p99 latency, action/primitive distributions, dispatch failures, tracking-loss count, cursor update Hz, movement coverage, and move-gap p95; success-rate, jitter, freeze, and false-positive classification still need scenario labels from manual protocols.
- Coverage target: 100% of new state-machine and safety policy branches; documented exceptions only for hardware-only paths.
- Current automated command: `uv run python -m unittest discover`.

## Manual Testing
- Validate camera selection and startup with `live --preview` and a hand visible in frame until `hand_frames > 0` and `preview_frames > 0`.
- If `hand_frames=0`, capture `camera-snapshot` and inspect the saved frame for wrong camera source, dark image, blur, or framing problems.
- Validate `live --preview --log C:\tmp\touchless-session.jsonl` with a hand visible until the preview shows landmarks, pinch line, counters, and `Pointing`, then move/pinch/scroll until action badge/`commands > 0`, `log_records > 0`, and the overlay state changes are visible.
- If cursor direction is still wrong for a specific camera, retest with `--no-invert-x` or `--invert-y`.
- Latest local dry-run reached `hand_frames=60` and `commands=0`; next manual step is moving/pinching/scrolling a visible hand in frame until commands are emitted.
- Validate overlay state transitions.
- Validate calibration flow with at least two users or repeated sessions.
- Validate Windows `SendInput` behavior against normal and elevated target windows.
- Validate Linux virtual device permissions and fallback errors.

## Performance Testing
- Measure frame capture, perception, normalization, interaction, queue, OS dispatch, overlay, and logging stages separately.
- Prefer latest-frame processing; reject designs that build unbounded frame queues.
- Product acceptance requires cursor update p95 gap < 50 ms during active movement, movement coverage >= 80%, effective tracking FPS >= 30, stationary jitter <= 6 px RMS, and no cursor freeze > 150 ms.

## Bug Tracking
- Severity 1: stuck mouse-down, action while paused/tracking lost, uncontrolled scroll, crash during OS injection.
- Severity 2: false click/drag above acceptance threshold, p95 latency above 80 ms, recovery above 2 seconds.
- Severity 3: overlay mismatch, incomplete log fields, calibration discomfort.
