---
phase: monitoring
title: Touchless Control MVP Monitoring and Observability
description: Runtime metrics, log handling, health checks, and incident response
---

# Touchless Control MVP Monitoring and Observability

## Observability model

The MVP is an offline desktop application, so monitoring is session-based rather than service/APM-based. The live preview provides immediate diagnostics, JSONL logs preserve per-frame evidence, and `main.py report` summarizes a completed session.

## Key metrics and thresholds

| Metric | Product gate | Source |
|---|---:|---|
| p95 end-to-end latency | <= 80 ms | Session log/report |
| Effective tracking rate | >= 30 FPS | Session report/live overlay |
| Movement coverage | >= 80% | Labeled movement scenarios |
| p95 movement gap | <= 50 ms | Labeled movement scenarios |
| Maximum active-movement freeze | <= 150 ms | Labeled movement scenarios |
| Stationary cursor jitter | <= 6 px RMS | `move-stationary` cursor deltas |
| Dispatch failures | 0 | Dispatch results/report |
| False clicks | <= 0.5/min | Manual idle/pointing protocol |
| False drags | <= 2 per 100 short clicks | Manual click protocol |

Supporting diagnostics include camera read failures, stale hand-frame count, tracking-loss count, cursor update Hz, primitive/action distributions, calibration status, and p99 latency.

## Logging

Enable a per-session JSONL log with `live --log <path>`. Each record includes timestamp, interaction state, primitives, transition reasons, emitted actions and cursor deltas, dispatch outcomes/error codes, latency, selected normalized hand features, and optional scenario label.

Generate a summary with:

```powershell
uv run python main.py report --log "C:\path\to\session.jsonl"
```

Retention guidance:

- Keep failed acceptance logs until the root cause and regression fixture are captured.
- Delete routine successful logs after the evidence is recorded in the testing document.
- Do not store raw camera frames by default.
- Treat normalized hand features and user-specific calibration profiles as local user data.

## Health checks

### Startup

```powershell
uv run python main.py camera-smoke --frames 30 --camera-index 0 --model "C:\path\to\hand_landmarker.task"
```

Healthy startup requires `success=True`, frames read above zero, and no `camera_open_failed` or `camera_read_failed` error.

### Runtime

A healthy dry-run session has:

- detected hand frames and rendered preview frames;
- no repeated stale-frame dispatch;
- zero dispatch failures;
- stable pointing without false click/drag actions;
- p95 latency and effective FPS within budget.

### Post-session

Run the report and compare only the metrics relevant to the selected scenario. A stationary-only log is not expected to have movement coverage/gap values; a movement-only log is not sufficient to sign off stationary jitter.

## Alert conditions

Critical conditions requiring immediate stop:

- stuck mouse-down or uncontrolled cursor/scroll output;
- any committed input while paused, no-hand, or tracking-lost;
- repeated dispatch failures against a supported target;
- camera/runtime crash during real dispatch.

Warning conditions requiring investigation before release:

- p95 latency above 80 ms;
- effective FPS below 30;
- stationary jitter above 6 px RMS;
- movement coverage/gap/freeze gate failure;
- tracking loss or camera read failures increasing across repeated runs;
- `calibration_status=uncalibrated` when a calibrated release is claimed.

## Incident response

1. Stop real dispatch and reproduce with `--dry-run`.
2. Preserve the exact command, platform/camera/model/preset configuration, relevant JSONL log, and terminal error code.
3. Classify the failure as perception, feature extraction, interaction safety, pointer mapping, queue/dispatch, preview, or logging/reporting.
4. Compare against a known-good scenario and change one variable at a time.
5. Add a failing automated regression when the failure can be represented without hardware.
6. Verify the fix with focused tests, mutation/regression evidence, the full suite, and the affected manual scenario.
7. Update implementation/testing docs with the root cause, fix, and remaining hardware limitations.

Known open operational blockers are elevated Windows `SendInput`, real Linux `/dev/uinput` integration, fresh post-quiet-bridge movement acceptance, repeated stationary protocols, and end-to-end calibration loading.
