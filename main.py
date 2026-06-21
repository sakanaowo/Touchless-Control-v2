from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from touchless_control.camera import CameraSmokeRunner, CameraSnapshotRunner
from touchless_control.observability import SessionReport, analyze_session_log
from touchless_control.runtime import LiveRunner


def main(
    argv: Sequence[str] | None = None,
    *,
    runner_factory: Callable[..., CameraSmokeRunner] = CameraSmokeRunner,
    snapshot_runner_factory: Callable[..., CameraSnapshotRunner] = CameraSnapshotRunner,
    live_runner_factory: Callable[..., LiveRunner] = LiveRunner,
    report_factory: Callable[[str], SessionReport] = analyze_session_log,
    print_fn: Callable[[str], None] = print,
) -> int:
    parser = argparse.ArgumentParser(prog="touchless-control")
    subparsers = parser.add_subparsers(dest="command", required=True)
    camera_smoke = subparsers.add_parser("camera-smoke")
    camera_smoke.add_argument("--camera-index", type=int, default=0)
    camera_smoke.add_argument("--frames", type=int, default=90)
    camera_smoke.add_argument("--width", type=int, default=640)
    camera_smoke.add_argument("--height", type=int, default=480)
    camera_smoke.add_argument("--model", default=None)
    camera_snapshot = subparsers.add_parser("camera-snapshot")
    camera_snapshot.add_argument("--camera-index", type=int, default=0)
    camera_snapshot.add_argument("--output", required=True)
    live = subparsers.add_parser("live")
    live.add_argument("--camera-index", type=int, default=0)
    live.add_argument("--frames", type=int, default=0)
    live.add_argument("--width", type=int, default=640)
    live.add_argument("--height", type=int, default=480)
    live.add_argument("--preview-width", type=int, default=960)
    live.add_argument("--preview-height", type=int, default=720)
    live.add_argument("--camera-fps", type=int, default=60)
    live.add_argument("--model", default=None)
    live.add_argument("--dry-run", action="store_true")
    live.add_argument("--preview", action="store_true")
    live.add_argument("--preset", choices=("gentle", "balanced", "responsive"), default="responsive")
    live.add_argument("--invert-x", action=argparse.BooleanOptionalAction, default=True)
    live.add_argument("--invert-y", action=argparse.BooleanOptionalAction, default=False)
    live.add_argument("--cursor-gain-scale", type=float, default=1.25)
    live.add_argument("--poll-timeout-ms", type=int, default=20)
    live.add_argument("--poll-interval-ms", type=int, default=2)
    live.add_argument("--max-read-failures", type=int, default=10)
    live.add_argument("--verbose-mediapipe", action="store_true")
    live.add_argument("--log", dest="log_path", default=None)
    report = subparsers.add_parser("report")
    report.add_argument("--log", required=True)

    args = parser.parse_args(argv)
    if args.command == "camera-smoke":
        runner = runner_factory(
            camera_index=args.camera_index,
            image_width=args.width,
            image_height=args.height,
            model_asset_path=args.model,
        )
        result = runner.run(max_frames=args.frames)
        print_fn(
            "camera_smoke "
            f"success={result.success} "
            f"frames_read={result.frames_read} "
            f"hand_frames={result.hand_frames} "
            f"error_code={result.error_code}"
        )
        return 0 if result.success else 1

    if args.command == "camera-snapshot":
        runner = snapshot_runner_factory(camera_index=args.camera_index)
        result = runner.run(output_path=args.output)
        print_fn(
            "camera_snapshot "
            f"success={result.success} "
            f"frames_read={result.frames_read} "
            f"output={result.output_path} "
            f"error_code={result.error_code}"
        )
        return 0 if result.success else 1

    if args.command == "live":
        runner = live_runner_factory(
            camera_index=args.camera_index,
            image_width=args.width,
            image_height=args.height,
            preview_width=args.preview_width,
            preview_height=args.preview_height,
            camera_fps=args.camera_fps,
            model_asset_path=args.model,
            dry_run=args.dry_run,
            preview=args.preview,
            preset_name=args.preset,
            invert_x=args.invert_x,
            invert_y=args.invert_y,
            cursor_gain_scale=args.cursor_gain_scale,
            poll_timeout_ms=args.poll_timeout_ms,
            poll_interval_ms=args.poll_interval_ms,
            max_read_failures=args.max_read_failures,
            suppress_native_logs=not args.verbose_mediapipe,
            log_path=args.log_path,
        )
        result = runner.run(max_frames=args.frames)
        print_fn(
            "live "
            f"success={result.success} "
            f"mode={'dry_run' if args.dry_run else 'dispatch'} "
            f"backend={result.backend} "
            f"frames_read={result.frames_read} "
            f"read_failures={result.read_failures} "
            f"hand_frames={result.hand_frames} "
            f"commands={result.commands_emitted} "
            f"dispatches={result.dispatches} "
            f"failures={result.failures} "
            f"log_records={result.log_records} "
            f"preview_frames={result.preview_frames} "
            f"p95_latency_ms={result.p95_latency_ms} "
            f"log_path={result.log_path} "
            f"error_code={result.error_code}"
        )
        return 0 if result.success else 1

    if args.command == "report":
        report_result = report_factory(args.log)
        for line in report_result.to_lines():
            print_fn(line)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
