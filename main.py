from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from touchless_control.camera import CameraSmokeRunner


def main(
    argv: Sequence[str] | None = None,
    *,
    runner_factory: Callable[..., CameraSmokeRunner] = CameraSmokeRunner,
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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
