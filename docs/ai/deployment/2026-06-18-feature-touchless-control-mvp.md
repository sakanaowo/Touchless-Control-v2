---
phase: deployment
title: Touchless Control MVP Deployment Strategy
description: Local desktop release, validation, rollback, and environment guidance
---

# Touchless Control MVP Deployment Strategy

## Deployment model

Touchless Control is a local desktop process, not a hosted service. The MVP is deployed from a pinned repository revision into a Python 3.12 environment managed by `uv`. Camera frames and mouse dispatch stay on the target machine.

Supported release targets:

- Windows 11: primary validation platform; normal-integrity `SendInput` is implemented.
- Linux: controller payload mapping is implemented, but the real `/dev/uinput` writer and permission setup remain incomplete.

External runtime asset:

- A compatible MediaPipe `hand_landmarker.task` file must be supplied outside the repository through `--model` or `TOUCHLESS_HAND_LANDMARKER_MODEL`.

## Build and verification gates

From a clean checkout:

```powershell
uv sync --frozen
uv run python -m unittest discover
npx ai-devkit@latest lint --feature touchless-control-mvp
```

A release candidate must also pass:

1. `camera-smoke` with the target camera/model.
2. A previewed `live --dry-run` session with a detected hand and zero dispatch failures.
3. Scenario-labeled movement and stationary reports against product thresholds.
4. Normal-integrity Windows dispatch on a disposable target window.
5. The remaining elevated and cross-OS manual matrix before claiming full platform support.

## Environment configuration

| Setting | Development/default | Release guidance |
|---|---|---|
| Python | 3.12 | Keep the `.python-version` and lockfile pin |
| Model | Explicit `--model` path | Store outside Git and verify the selected asset |
| Camera | Index 0, 640x480, 60 FPS request | Validate actual FPS and framing per machine |
| Pointer preset | `responsive` | Start from default; tune only with paired movement/stationary evidence |
| Dispatch | `--dry-run` | Enable real dispatch only after preview validation |
| Logging | Optional JSONL path | Use a per-session path with controlled retention |

No database, cloud account, API key, or migration is required for the MVP.

## Release procedure

1. Confirm a clean worktree and record the release commit SHA.
2. Run the automated verification gates.
3. Synchronize the environment with `uv sync --frozen`.
4. Provision the hand-landmarker model outside the repository.
5. Run camera smoke and dry-run preview on the target machine.
6. Capture and report the required acceptance scenarios.
7. Validate real dispatch against a disposable normal-integrity target.
8. Record platform, camera, model identity, preset, command, log paths, and results in the testing document.
9. Promote the same commit only after all gates required for the claimed platform are complete.

## Rollback

Rollback triggers include uncontrolled cursor movement, stuck mouse-down, actions during paused/tracking-lost states, regression in stationary jitter, dispatch failures, or p95 latency above budget.

Rollback options, in order:

1. Stop the process or restore `--dry-run`.
2. Use `--legacy-cursor` for a pointer-only comparison/temporary fallback.
3. Return to the last verified Git commit and run `uv sync --frozen`.
4. Re-run camera smoke and dry-run validation before re-enabling dispatch.

Use `git revert <commit>` for a shared-history rollback; do not rewrite published history.

## Security and privacy

- Real input injection can affect the active desktop; test with a disposable target and keep a physical escape path.
- Elevated Windows injection must remain disabled as a release claim until Task 4.8 passes.
- JSONL logs contain normalized hand features, states, actions, and outcomes. They do not contain raw camera images by default, but still require controlled storage and retention.
- Do not commit model assets, local session logs, or user-specific calibration profiles unless they are deliberately sanitized fixtures.
