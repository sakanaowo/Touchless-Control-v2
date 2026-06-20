import unittest

from touchless_control.camera import CameraSmokeResult


class _Runner:
    def __init__(self, result: CameraSmokeResult) -> None:
        self.result = result
        self.max_frames = None

    def run(self, *, max_frames: int):
        self.max_frames = max_frames
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


if __name__ == "__main__":
    unittest.main()
