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
    def __init__(self, hand_after_frames: int = 1, poll_results=None) -> None:
        self.submitted = []
        self.hand_after_frames = hand_after_frames
        self.poll_results = list(poll_results or [])

    def submit(self, frame, timestamp_ms: int) -> None:
        self.submitted.append((frame, timestamp_ms))

    def poll_latest(self):
        if self.poll_results:
            return self.poll_results.pop(0)
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

    def test_waits_briefly_for_async_perception_result(self) -> None:
        from touchless_control.camera import CameraSmokeRunner

        capture = _Capture(frames=["frame-1"])
        perception = _Perception(poll_results=[None, object()])
        sleeps = []
        runner = CameraSmokeRunner(
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            timestamp_ms=lambda: 100,
            poll_timeout_ms=5,
            poll_interval_ms=1,
            sleep_ms=sleeps.append,
        )

        result = runner.run(max_frames=1)

        self.assertEqual(result.hand_frames, 1)
        self.assertEqual(sleeps, [1])

    def test_reports_camera_open_failure_without_crashing(self) -> None:
        from touchless_control.camera import CameraSmokeRunner

        runner = CameraSmokeRunner(
            capture_factory=lambda _index: _ClosedCapture(frames=[]),
            perception_factory=lambda _width, _height: _Perception(),
        )

        result = runner.run(max_frames=1)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "camera_open_failed")


class CameraSnapshotRunnerTests(unittest.TestCase):
    def test_saves_one_camera_frame_to_output_path(self) -> None:
        from touchless_control.camera import CameraSnapshotRunner

        saved = []
        capture = _Capture(frames=["frame-1"])
        runner = CameraSnapshotRunner(
            capture_factory=lambda _index: capture,
            frame_writer=lambda path, frame: saved.append((path, frame)) or True,
        )

        result = runner.run(output_path="C:/tmp/frame.jpg")

        self.assertTrue(result.success)
        self.assertTrue(capture.released)
        self.assertEqual(result.frames_read, 1)
        self.assertEqual(result.output_path, "C:/tmp/frame.jpg")
        self.assertEqual(saved, [("C:/tmp/frame.jpg", "frame-1")])

    def test_reports_snapshot_write_failure(self) -> None:
        from touchless_control.camera import CameraSnapshotRunner

        runner = CameraSnapshotRunner(
            capture_factory=lambda _index: _Capture(frames=["frame-1"]),
            frame_writer=lambda _path, _frame: False,
        )

        result = runner.run(output_path="C:/tmp/frame.jpg")

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "snapshot_write_failed")


if __name__ == "__main__":
    unittest.main()
