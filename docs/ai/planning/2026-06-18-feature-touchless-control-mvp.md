---
phase: planning
title: Touchless Control MVP Task Plan
description: Initial task breakdown for the touchless mouse-control MVP
---

# Touchless Control MVP Task Plan

## Milestones
- [x] Milestone 1: Perception and feature-contract foundation.
- [x] Milestone 2: Safe interaction state machine and cursor mapping.
- [x] Milestone 3: OS dispatch, overlay, logging, calibration, and acceptance validation.
- [ ] Milestone 4: Product-grade pointer control and end-user acceptance.

## Task Breakdown
### Phase 1: Foundation
- [x] Task 1.1: Remove obsolete reference repositories from the product branch.
- [x] Task 1.2: Define Python package/module layout for perception, features, interaction, control, presentation, observability, and config.
- [x] Task 1.3: Add dataclass or typed contracts for `HandFrame`, `FeatureFrame`, `PrimitiveEvent`, `InteractionEvent`, `ActionCommand`, and `OSDispatchResult`.
- [x] Task 1.4: Add landmark fixtures for unit and integration tests.

### Phase 2: Core Interaction
- [x] Task 2.1: Implement MediaPipe perception adapter with one-hand configuration.
- [x] Task 2.2: Implement normalization and stability/pinch/velocity feature extraction.
- [x] Task 2.3: Implement primitive detector with hysteresis.
- [x] Task 2.4: Implement state machine with `NoHand`, `Pointing`, `ClickCandidate`, `ClickCommitted`, `Dragging`, `Scrolling`, `Paused`, `TrackingLost`, and `Cooldown`.
- [x] Task 2.5: Implement relative cursor mapping with deadzone, smoothing, acceleration, and clamping.

### Phase 3: Integration & Polish
- [x] Task 3.1: Implement Windows and Linux mouse-controller backends behind one interface.
- [x] Task 3.2: Implement action queue and safe release behavior.
- [x] Task 3.3: Implement overlay state feedback and latency warnings.
- [x] Task 3.4: Implement structured session logging and summary metrics.
- [x] Task 3.5: Implement sensitivity presets and initial calibration.
- [x] Task 3.6: Implement automated acceptance checks and threshold tuning hooks; manual hardware acceptance remains in the testing plan.
- [x] Task 3.7: Implement live runtime CLI that connects camera, MediaPipe, feature normalization, pipeline, OS dispatch, dry-run mode, preview overlay, and JSONL session logging for human testing.
- [x] Task 3.8: Implement session report CLI for JSONL latency, FPS, action, primitive, failure, and tracking-loss summaries.
- [x] Task 3.9: Tune live window testing ergonomics with responsive preset wiring, horizontal cursor inversion, larger default preview resolution, and transient camera read-failure tolerance.
- [x] Task 3.10: Decouple capture resolution from preview window size, make the preview window resizable, draw landmarks against the actual frame size, configure low-latency camera FPS/buffer properties, and expose cursor gain scaling.
- [x] Task 3.11: Prevent stale MediaPipe live-stream outputs from driving cursor dispatch and keep the default preview aspect ratio aligned with 640x480 capture.

### Phase 4: Product-Grade Pointer Control
- [x] Task 4.1: Add product acceptance metrics for cursor update cadence, movement coverage, and move gaps to the session report.
- [x] Task 4.2: Add residual/subpixel accumulation in cursor mapping so small intentional hand motion is not dropped by the deadzone.
- [ ] Task 4.3: Replace velocity-only mapping with a dedicated pointer engine that combines position, velocity, residual movement, adaptive deadzone, and virtual-trackpad bounds.
- [ ] Task 4.4: Add calibration workflow for neutral zone, control region, per-user gain curve, and direction validation.
- [ ] Task 4.5: Add scenario-labeled product acceptance logs for slow precise movement, stop-and-hold jitter, straight-line movement, click stability, drag stability, and long-session control.
- [ ] Task 4.6: Implement product acceptance gates: cursor update p95 gap < 50 ms during active movement, movement coverage >= 80%, effective tracking FPS >= 30, stationary jitter <= 6 px RMS, and no cursor freeze > 150 ms.
- [ ] Task 4.7: Add runtime diagnostics overlay for cursor update Hz, move gap p95, movement coverage, frame drop/stale counts, and calibration status.
- [ ] Task 4.8: Tune Windows dispatch path for high-rate movement and verify against normal/elevated target windows.

## Dependencies
- Requirements and design docs must be reviewed before implementation starts.
- State machine and action contracts should land before OS backend wiring.
- Mock OS controller should land before real OS injection tests.
- Calibration and threshold tuning depend on logging and metrics.

## Timeline & Estimates
- Foundation: 1-2 development sessions.
- Core interaction: 3-5 development sessions.
- Integration, OS backends, and observability: 3-5 development sessions.
- Hardware/manual acceptance testing and threshold tuning: 2-3 sessions.
- Product-grade pointer control and acceptance hardening: 4-8 development sessions.

## Risks & Mitigation
- Tracking jitter or motion blur causes false actions: use hysteresis, deadzone, smoothing, cooldown, and safe states.
- OS injection can be unsafe: test through mock backends first and enforce safe release.
- Latency can grow from blocking queues: prioritize latest-frame freshness and measure stage timing.
- Product pointer quality is not proven by low latency alone: require cursor cadence, movement coverage, jitter, and scenario-labeled acceptance metrics before treating the app as end-user ready.
- Linux permissions may vary: document `/dev/uinput` requirements and report backend errors clearly.
- User fatigue can hurt usability: provide clutch, sensitivity presets, and calibration.

## Current Product Acceptance Status
- Latest checked log: `C:\tmp\touchless-session.jsonl`.
- Stale-frame regression is fixed in the latest implementation slice, but the current logged product metrics remain unacceptable: `effective_fps=15.48`, `cursor_update_hz=5.05`, `movement_coverage=0.33`, `move_gap_p95_ms=516.0`.
- Next implementation focus is Task 4.3 and Task 4.4. Task 4.1 and Task 4.2 are first slices only; they do not complete product-grade pointer control.

## Resources Needed
- Windows machine for `SendInput` validation.
- Linux machine with `/dev/uinput` access for backend validation.
- Webcam with normal indoor lighting.
- Landmark fixtures and manual test protocol derived from `docs/references/touchless spec.md`.
