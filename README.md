# Touchless Control v2

Touchless Control is a Python desktop input prototype that turns one webcam-tracked hand into relative mouse movement, click, drag, scroll, and pause/clutch actions. The runtime uses MediaPipe Hands, a safety-first interaction state machine, structured JSONL logs, and platform-specific mouse-controller boundaries.

## Current status

- Python 3.12 is required.
- Windows `SendInput` works against normal-integrity applications.
- Dry-run camera, preview, logging, reporting, and automated pointer acceptance metrics are available.
- Elevated Windows targets, the real Linux `/dev/uinput` writer, end-to-end calibration loading, and the full manual acceptance matrix remain open.
- Real OS dispatch is intentionally separate from the safer `--dry-run` workflow.

## Setup

Install `uv`, then create/synchronize the project environment:

```powershell
uv sync
```

MediaPipe Tasks requires a compatible `hand_landmarker.task` model. Pass its path with `--model` or set it for the current PowerShell session:

```powershell
$env:TOUCHLESS_HAND_LANDMARKER_MODEL = "C:\path\to\hand_landmarker.task"
```

The model file is not stored in this repository.

## Safe first run

Confirm the camera and model initialize without injecting mouse input:

```powershell
uv run python main.py camera-smoke --frames 30 --camera-index 0 --model "C:\path\to\hand_landmarker.task"
```

Run the complete observable pipeline in dry-run mode:

```powershell
uv run python main.py live --frames 300 --dry-run --preview --model "C:\path\to\hand_landmarker.task" --log "C:\tmp\touchless-session.jsonl"
```

Expected terminal output includes `success=True`, `mode=dry_run`, frame/hand/command counts, zero dispatch failures, and the log path. The preview can be stopped with its quit key.

Analyze the recorded session:

```powershell
uv run python main.py report --log "C:\tmp\touchless-session.jsonl"
```

## Product acceptance scenarios

`live --scenario` accepts:

- `move-slow-precise`
- `move-stationary`
- `move-straight`
- `click-stability`
- `drag-stability`
- `long-session`

Example:

```powershell
uv run python main.py live --frames 300 --dry-run --preview --scenario move-straight --model "C:\path\to\hand_landmarker.task" --log "C:\tmp\move-straight.jsonl"
```

Pointer acceptance targets are p95 latency at most 80 ms, effective tracking rate at least 30 FPS, movement coverage at least 80%, p95 movement gap at most 50 ms, stationary jitter at most 6 px RMS, and no active-movement freeze above 150 ms.

## Real mouse dispatch

Remove `--dry-run` only after the preview and scenario logs are correct:

```powershell
uv run python main.py live --frames 300 --preview --model "C:\path\to\hand_landmarker.task"
```

Use a disposable target window first. The Windows backend uses relative `SendInput`; elevated-target validation is still open. Linux auto-detection currently requires an injected writer and is not an end-user runtime path yet.

## Verification

```powershell
uv run python -m unittest discover
npx ai-devkit@latest lint --feature touchless-control-mvp
```

## Architecture

- `touchless_control/vision`: camera and MediaPipe perception.
- `touchless_control/interaction`: primitives and safety state machine.
- `touchless_control/control`: pointer engine, queue, calibration, and OS backends.
- `touchless_control/runtime`: live orchestration and pipeline integration.
- `touchless_control/observability`: JSONL logging, reports, and acceptance gates.
- `touchless_control/presentation`: preview and overlay diagnostics.

Detailed feature records live under `docs/ai/`, especially the [task plan](docs/ai/planning/2026-06-18-feature-touchless-control-mvp.md), [testing strategy](docs/ai/testing/2026-06-18-feature-touchless-control-mvp.md), and [implementation guide](docs/ai/implementation/2026-06-18-feature-touchless-control-mvp.md).
