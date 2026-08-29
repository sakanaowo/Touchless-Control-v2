import unittest

from touchless_control.camera import CameraSmokeResult, CameraSnapshotResult
from touchless_control.observability import SessionReport
from touchless_control.runtime.live import LiveRunResult


class _Runner:
    def __init__(self, result: CameraSmokeResult) -> None:
        self.result = result
        self.max_frames = None

    def run(self, *, max_frames: int):
        self.max_frames = max_frames
        return self.result


class _LiveRunner:
    def __init__(self, result: LiveRunResult) -> None:
        self.result = result
        self.max_frames = None

    def run(self, *, max_frames: int):
        self.max_frames = max_frames
        return self.result


class _SnapshotRunner:
    def __init__(self, result: CameraSnapshotResult) -> None:
        self.result = result
        self.output_path = None

    def run(self, *, output_path: str):
        self.output_path = output_path
        return self.result


class MainCliTests(unittest.TestCase):
    def test_camera_smoke_command_runs_runner_and_reports_summary(self) -> None:
        from main import main

        output = []
        runner = _Runner(CameraSmokeResult(success=True, frames_read=2, hand_frames=1))

        exit_code = main(
            ["camera-smoke", "--frames", "2"],
            runner_factory=lambda **_kwargs: runner,
            print_fn=output.append,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(runner.max_frames, 2)
        self.assertIn("frames_read=2", output[0])
        self.assertIn("hand_frames=1", output[0])

    def test_camera_smoke_command_returns_nonzero_on_failure(self) -> None:
        from main import main

        output = []
        runner = _Runner(
            CameraSmokeResult(
                success=False,
                frames_read=0,
                hand_frames=0,
                error_code="camera_open_failed",
            )
        )

        exit_code = main(
            ["camera-smoke"],
            runner_factory=lambda **_kwargs: runner,
            print_fn=output.append,
        )

        self.assertEqual(exit_code, 1)
        self.assertIn("camera_open_failed", output[0])

    def test_camera_snapshot_command_runs_runner_and_reports_summary(self) -> None:
        from main import main

        output = []
        runner = _SnapshotRunner(
            CameraSnapshotResult(
                success=True,
                frames_read=1,
                output_path="C:/tmp/touchless-frame.jpg",
            )
        )

        exit_code = main(
            ["camera-snapshot", "--output", "C:/tmp/touchless-frame.jpg"],
            snapshot_runner_factory=lambda **_kwargs: runner,
            print_fn=output.append,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(runner.output_path, "C:/tmp/touchless-frame.jpg")
        self.assertIn("camera_snapshot success=True", output[0])
        self.assertIn("output=C:/tmp/touchless-frame.jpg", output[0])

    def test_live_command_runs_live_runner_and_reports_summary(self) -> None:
        from main import main

        output = []
        captured_kwargs = {}
        runner = _LiveRunner(
            LiveRunResult(
                success=True,
                frames_read=3,
                hand_frames=2,
                commands_emitted=1,
                dispatches=1,
                failures=0,
                backend="dry_run",
                log_records=2,
                preview_frames=3,
                p95_latency_ms=12.0,
            )
        )

        exit_code = main(
            ["live", "--frames", "3", "--dry-run", "--preview", "--log", "C:/tmp/session.jsonl"],
            live_runner_factory=lambda **kwargs: captured_kwargs.update(kwargs) or runner,
            print_fn=output.append,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(runner.max_frames, 3)
        self.assertEqual(captured_kwargs["image_width"], 640)
        self.assertEqual(captured_kwargs["image_height"], 480)
        self.assertEqual(captured_kwargs["preview_width"], 960)
        self.assertEqual(captured_kwargs["preview_height"], 720)
        self.assertEqual(captured_kwargs["camera_fps"], 60)
        self.assertEqual(captured_kwargs["preset_name"], "responsive")
        self.assertTrue(captured_kwargs["invert_x"])
        self.assertFalse(captured_kwargs["invert_y"])
        self.assertEqual(captured_kwargs["cursor_gain_scale"], 1.25)
        self.assertEqual(captured_kwargs["max_read_failures"], 10)
        self.assertTrue(captured_kwargs["suppress_native_logs"])
        self.assertTrue(captured_kwargs["preview"])
        self.assertEqual(captured_kwargs["log_path"], "C:/tmp/session.jsonl")
        self.assertIn("live success=True", output[0])
        self.assertIn("mode=dry_run", output[0])
        self.assertIn("backend=dry_run", output[0])
        self.assertIn("hand_frames=2", output[0])
        self.assertIn("commands=1", output[0])
        self.assertIn("log_records=2", output[0])
        self.assertIn("preview_frames=3", output[0])
        self.assertIn("p95_latency_ms=12.0", output[0])

    def test_live_command_can_enable_verbose_mediapipe_logs(self) -> None:
        from main import main

        captured_kwargs = {}
        runner = _LiveRunner(
            LiveRunResult(
                success=True,
                frames_read=1,
                hand_frames=0,
                commands_emitted=0,
                dispatches=0,
                failures=0,
            )
        )

        main(
            ["live", "--frames", "1", "--verbose-mediapipe"],
            live_runner_factory=lambda **kwargs: captured_kwargs.update(kwargs) or runner,
            print_fn=lambda _message: None,
        )

        self.assertFalse(captured_kwargs["suppress_native_logs"])

    def test_live_command_forwards_product_acceptance_scenario(self) -> None:
        from main import main

        captured_kwargs = {}
        runner = _LiveRunner(
            LiveRunResult(
                success=True,
                frames_read=1,
                hand_frames=0,
                commands_emitted=0,
                dispatches=0,
                failures=0,
            )
        )

        exit_code = main(
            ["live", "--frames", "1", "--scenario", "move-slow-precise"],
            live_runner_factory=lambda **kwargs: captured_kwargs.update(kwargs) or runner,
            print_fn=lambda _message: None,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured_kwargs["scenario_label"], "move-slow-precise")

    def test_live_command_exposes_window_tuning_flags(self) -> None:
        from main import main

        captured_kwargs = {}
        runner = _LiveRunner(
            LiveRunResult(
                success=True,
                frames_read=1,
                hand_frames=0,
                commands_emitted=0,
                dispatches=0,
                failures=0,
            )
        )

        main(
            [
                "live",
                "--frames",
                "1",
                "--width",
                "1280",
                "--height",
                "720",
                "--preview-width",
                "1024",
                "--preview-height",
                "768",
                "--camera-fps",
                "30",
                "--preset",
                "balanced",
                "--no-invert-x",
                "--invert-y",
                "--cursor-gain-scale",
                "1.5",
                "--poll-timeout-ms",
                "8",
                "--poll-interval-ms",
                "1",
                "--max-read-failures",
                "3",
            ],
            live_runner_factory=lambda **kwargs: captured_kwargs.update(kwargs) or runner,
            print_fn=lambda _message: None,
        )

        self.assertEqual(captured_kwargs["image_width"], 1280)
        self.assertEqual(captured_kwargs["image_height"], 720)
        self.assertEqual(captured_kwargs["preview_width"], 1024)
        self.assertEqual(captured_kwargs["preview_height"], 768)
        self.assertEqual(captured_kwargs["camera_fps"], 30)
        self.assertEqual(captured_kwargs["preset_name"], "balanced")
        self.assertFalse(captured_kwargs["invert_x"])
        self.assertTrue(captured_kwargs["invert_y"])
        self.assertEqual(captured_kwargs["cursor_gain_scale"], 1.5)
        self.assertEqual(captured_kwargs["poll_timeout_ms"], 8)
        self.assertEqual(captured_kwargs["poll_interval_ms"], 1)
        self.assertEqual(captured_kwargs["max_read_failures"], 3)

    def test_report_command_reads_session_log_and_prints_summary(self) -> None:
        from main import main

        output = []
        captured_paths = []
        report = SessionReport(
            total_records=2,
            duration_s=1.0,
            effective_fps=2.0,
            action_count=1,
            dispatch_count=1,
            failure_count=0,
            tracking_loss_count=0,
            p95_latency_ms=12.0,
            p99_latency_ms=12.0,
            primitive_counts={"pointing": 2},
            action_counts={"move_relative": 1},
        )

        exit_code = main(
            ["report", "--log", "C:/tmp/touchless-session.jsonl"],
            report_factory=lambda path: captured_paths.append(path) or report,
            print_fn=output.append,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured_paths, ["C:/tmp/touchless-session.jsonl"])
        self.assertIn("session_report total_records=2", output[0])
        self.assertIn("primitives pointing=2", output[1])
        self.assertIn("actions move_relative=1", output[2])


if __name__ == "__main__":
    unittest.main()
