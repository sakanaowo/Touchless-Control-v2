---
phase: requirements
title: Touchless Control MVP Requirements
description: Requirements for a camera-based, touchless mouse-control input device MVP
---

# Touchless Control MVP Requirements

## Problem Statement
Physical mouse or touch input is not always convenient, hygienic, or accessible in presentation, kiosk, hands-busy, and basic accessibility contexts. The product needs to turn a commodity camera into a safe touchless pointing device.

The system is not a frame-by-frame gesture classifier. It is a real-time input device pipeline: continuous hand tracking, normalized feature extraction, interaction-state inference, safe action commit, OS mouse-event dispatch, feedback, and logging.

The source of truth for this feature is `docs/references/touchless spec.md`. The two nested reference repositories previously used for exploration are no longer product inputs and must not be treated as dependencies, architecture sources, or implementation targets.

## Goals & Objectives
- Build an MVP that supports cursor movement, left click, drag, vertical scroll, pause/clutch, visual feedback, logging, sensitivity presets, calibration, and Windows/Linux mouse backends.
- Use MediaPipe hand tracking as the perception baseline; do not train a custom model for MVP.
- Use relative cursor mapping from normalized hand motion to OS mouse deltas.
- Route all committed actions through an interaction state machine and OS-controller abstraction.
- Optimize for safety: false clicks, false drags, and unsafe stuck mouse-down states are more harmful than missed actions.

Non-goals:
- Sign language recognition.
- General-purpose gesture classification.
- Multi-hand interaction.
- Right click, zoom, browser navigation gestures, or multi-user support.
- macOS support.
- Copying behavior or code from the removed reference repositories.

## User Stories & Use Cases
- As an end user, I want to move the cursor by moving my pointing hand so that I can control the desktop without touching a mouse.
- As an end user, I want to perform a left click with a short pinch so that I can select controls and links.
- As an end user, I want to drag by sustaining a pinch so that I can move windows or objects.
- As an end user, I want to scroll with a two-finger vertical swipe so that I can navigate documents and pages.
- As an end user, I want an open-palm pause/clutch state so that I can safely rest or reposition my hand.
- As QA, I want structured logs and session metrics so that false positives, missed actions, latency, and recovery can be measured repeatably.

Primary workflows:
- Move cursor: `NoHand` -> stable hand detected -> `Pointing` -> `move_relative` events.
- Left click: `Pointing` -> `ClickCandidate` on pinch close -> commit one click on valid release -> `Cooldown`.
- Drag: `Pointing` -> `ClickCandidate` -> `Dragging` after hold threshold or early drag motion -> safe `left_up` on release or tracking loss.
- Scroll: `Pointing` -> `Scrolling` on two-finger vertical swipe -> bounded wheel dispatch -> stop on finger release, pause, drag conflict, or tracking loss.
- Pause/clutch: any active interaction -> `Paused` on open palm -> no OS actions until stable pointing resumes.

## Success Criteria
- End-to-end latency from frame timestamp to OS dispatch completion is below 80 ms at p95.
- Effective processing rate is at least 30 FPS for 95% of a session; 45 FPS is the target.
- Left click action success rate is at least 95% in normal lighting.
- Drag and scroll action success rates are at least 90%.
- Overall false positives do not exceed 1.0 per minute in a five-minute mixed task.
- False click rate does not exceed 0.5 per minute in idle/pointing/reposition tests.
- False drag count is at most 2 per 100 short-click attempts.
- Recovery from `TrackingLost` to safe state is at most 2 seconds.
- No click, drag, or scroll events are committed while `Paused`, `NoHand`, or `TrackingLost`.
- Logs include timestamp, state, primitive, action, latency, important features, and outcome for committed actions and failure classes.

## Constraints & Assumptions
- Target operating systems are Windows and Linux.
- Windows backend uses `SendInput`; Linux backend uses `uinput` or a thin abstraction over it.
- MVP uses one hand only; `num_hands` should be 1.
- Relative mapping is required; absolute screen mapping is out of scope for MVP.
- Default threshold profile is balanced: `pinch_close_ratio <= 0.30`, `pinch_open_ratio >= 0.45`, `drag_hold_threshold = 280 ms`, `click_motion_guard = 0.04` palm-scale, `early_drag_motion_threshold = 0.12` palm-scale.
- Mapping defaults are `deadzone = 0.015` palm-scale, `base_gain = 900 px/palm-scale`, `accel_gain = 1600 px/palm-scale`, `v_ref = 0.10` palm-scale/frame, `gamma = 1.6`, `ema_alpha_slow = 0.22`, `ema_alpha_fast = 0.55`, `max_step = 120 px/frame`.
- Calibration should take roughly 20-30 seconds and tune user-specific jitter, pinch thresholds, and drag thresholds within safe bounds.
- The removed reference repositories are no longer part of the repository value stream; keeping them would add noise and should not block requirements work.

## Questions & Open Items
- Assumption accepted: feature name is `touchless-control-mvp`.
- Assumption accepted: MVP scope follows `docs/references/touchless spec.md`.
- Assumption accepted: the former reference repositories have been removed and are not needed for future implementation.
- Resolved in design review: scroll is represented as a dedicated `Scrolling` state for safety, feedback, cancellation, and logging.
- Deferred to implementation planning: exact module/package layout for the Python codebase.
