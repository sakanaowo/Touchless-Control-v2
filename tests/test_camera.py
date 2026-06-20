import unittest


class _Capture:
    def __init__(self, frames) -> None:
        self.frames = list(frames)
        self.released = False

    def isOpened(self) -> bool:
        return True

    def read(self):
        if not self.frames:
            return False, None
        return True, self.frames.pop(0)

    def release(self) -> None:
        self.released = True


class _ClosedCapture(_Capture):
    def isOpened(self) -> bool:
        return False


class _Perception:
    def __init__(self, hand_after_frames: int = 1) -> None:
        self.submitted = []
        self.hand_after_frames = hand_after_frames

    def submit(self, frame, timestamp_ms: int) -> None:
        self.submitted.append((frame, timestamp_ms))

    def poll_latest(self):
        if len(self.submitted) >= self.hand_after_frames:
            return object()
        return None


class CameraSmokeRunnerTests(unittest.TestCase):
    def test_reads_frames_and_reports_detected_hand(self) -> None:
        from touchless_control.camera import CameraSmokeRunner

        capture = _Capture(frames=["frame-1", "frame-2"])
        perception = _Perception(hand_after_frames=2)
        runner = CameraSmokeRunner(
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            timestamp_ms=lambda: 100,
        )

        result = runner.run(max_frames=2)

        self.assertTrue(result.success)
        self.assertEqual(result.frames_read, 2)
        self.assertEqual(result.hand_frames, 1)
        self.assertTrue(capture.released)
        self.assertEqual(perception.submitted, [("frame-1", 100), ("frame-2", 100)])

    def test_reports_camera_open_failure_without_crashing(self) -> None:
        from touchless_control.camera import CameraSmokeRunner

        runner = CameraSmokeRunner(
            capture_factory=lambda _index: _ClosedCapture(frames=[]),
            perception_factory=lambda _width, _height: _Perception(),
        )

        result = runner.run(max_frames=1)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "camera_open_failed")


if __name__ == "__main__":
    unittest.main()
