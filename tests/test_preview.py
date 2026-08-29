import sys
import unittest
from types import SimpleNamespace

from touchless_control.contracts import ActionCommand, HandFrame


class _Frame:
    def copy(self):
        return self


class _ShapedFrame:
    shape = (480, 640, 3)

    def copy(self):
        return self


class PreviewRendererTests(unittest.TestCase):
    def test_opencv_preview_close_before_render_does_not_destroy_missing_window(self) -> None:
        from touchless_control.presentation.preview import OpenCVPreviewRenderer

        calls = []
        fake_cv2 = SimpleNamespace(
            destroyWindow=lambda *args: calls.append(("destroyWindow", args)),
        )
        original_cv2 = sys.modules.get("cv2")
        sys.modules["cv2"] = fake_cv2
        try:
            OpenCVPreviewRenderer().close()
        finally:
            if original_cv2 is None:
                sys.modules.pop("cv2", None)
            else:
                sys.modules["cv2"] = original_cv2

        self.assertEqual(calls, [])

    def test_opencv_preview_draws_hand_landmarks_when_hand_frame_is_available(self) -> None:
        from touchless_control.presentation.preview import OpenCVPreviewRenderer

        calls = []
        fake_cv2 = SimpleNamespace(
            FONT_HERSHEY_SIMPLEX=0,
            LINE_AA=16,
            putText=lambda *args: calls.append(("putText", args)),
            rectangle=lambda *args: calls.append(("rectangle", args)),
            circle=lambda *args: calls.append(("circle", args)),
            line=lambda *args: calls.append(("line", args)),
            imshow=lambda *args: calls.append(("imshow", args)),
            waitKey=lambda _delay: ord("q"),
        )
        original_cv2 = sys.modules.get("cv2")
        sys.modules["cv2"] = fake_cv2
        try:
            hand_frame = HandFrame(
                timestamp_ms=1,
                image_width=640,
                image_height=480,
                landmarks_img=tuple((0.5, 0.25, 0.0) for _ in range(21)),
                landmarks_world=tuple((0.0, 0.0, 0.0) for _ in range(21)),
                handedness="Right",
                detection_confidence=0.9,
                presence_confidence=0.9,
                tracking_confidence=0.9,
            )

            stop_requested = OpenCVPreviewRenderer().render(
                _Frame(),
                None,
                commands=(),
                results=(),
                backend="dry_run",
                dry_run=True,
                hand_frame=hand_frame,
            )
        finally:
            if original_cv2 is None:
                sys.modules.pop("cv2", None)
            else:
                sys.modules["cv2"] = original_cv2

        self.assertTrue(stop_requested)
        self.assertTrue(any(name == "circle" for name, _args in calls))
        circle_call = next(args for name, args in calls if name == "circle")
        self.assertEqual(circle_call[1], (320, 120))

    def test_opencv_preview_uses_actual_frame_dimensions_for_landmarks(self) -> None:
        from touchless_control.presentation.preview import OpenCVPreviewRenderer

        calls = []
        fake_cv2 = SimpleNamespace(
            FONT_HERSHEY_SIMPLEX=0,
            LINE_AA=16,
            putText=lambda *args: calls.append(("putText", args)),
            rectangle=lambda *args: calls.append(("rectangle", args)),
            circle=lambda *args: calls.append(("circle", args)),
            line=lambda *args: calls.append(("line", args)),
            imshow=lambda *args: calls.append(("imshow", args)),
            waitKey=lambda _delay: -1,
        )
        original_cv2 = sys.modules.get("cv2")
        sys.modules["cv2"] = fake_cv2
        try:
            hand_frame = HandFrame(
                timestamp_ms=1,
                image_width=960,
                image_height=540,
                landmarks_img=tuple((0.5, 0.25, 0.0) for _ in range(21)),
                landmarks_world=tuple((0.0, 0.0, 0.0) for _ in range(21)),
                handedness="Right",
                detection_confidence=0.9,
                presence_confidence=0.9,
                tracking_confidence=0.9,
            )

            OpenCVPreviewRenderer().render(
                _ShapedFrame(),
                None,
                commands=(),
                results=(),
                backend="dry_run",
                dry_run=True,
                hand_frame=hand_frame,
            )
        finally:
            if original_cv2 is None:
                sys.modules.pop("cv2", None)
            else:
                sys.modules["cv2"] = original_cv2

        circle_call = next(args for name, args in calls if name == "circle")
        self.assertEqual(circle_call[1], (320, 120))

    def test_opencv_preview_creates_resizable_window_once(self) -> None:
        from touchless_control.presentation.preview import OpenCVPreviewRenderer

        calls = []
        fake_cv2 = SimpleNamespace(
            FONT_HERSHEY_SIMPLEX=0,
            LINE_AA=16,
            WINDOW_NORMAL=0,
            WINDOW_KEEPRATIO=16,
            namedWindow=lambda *args: calls.append(("namedWindow", args)),
            resizeWindow=lambda *args: calls.append(("resizeWindow", args)),
            putText=lambda *args: calls.append(("putText", args)),
            rectangle=lambda *args: calls.append(("rectangle", args)),
            circle=lambda *args: calls.append(("circle", args)),
            line=lambda *args: calls.append(("line", args)),
            imshow=lambda *args: calls.append(("imshow", args)),
            waitKey=lambda _delay: -1,
        )
        original_cv2 = sys.modules.get("cv2")
        sys.modules["cv2"] = fake_cv2
        try:
            renderer = OpenCVPreviewRenderer(preview_width=960, preview_height=720)
            renderer.render(
                _Frame(),
                None,
                commands=(),
                results=(),
                backend="dry_run",
                dry_run=True,
            )
            renderer.render(
                _Frame(),
                None,
                commands=(),
                results=(),
                backend="dry_run",
                dry_run=True,
            )
        finally:
            if original_cv2 is None:
                sys.modules.pop("cv2", None)
            else:
                sys.modules["cv2"] = original_cv2

        self.assertEqual(
            [name for name, _args in calls].count("namedWindow"),
            1,
        )
        named_window = next(args for name, args in calls if name == "namedWindow")
        self.assertEqual(named_window[1], 16)
        self.assertIn(("resizeWindow", ("Touchless Control Preview", 960, 720)), calls)

    def test_opencv_preview_displays_stats_action_badge_and_pinch_line(self) -> None:
        from touchless_control.presentation.preview import OpenCVPreviewRenderer, PreviewStats

        calls = []
        fake_cv2 = SimpleNamespace(
            FONT_HERSHEY_SIMPLEX=0,
            LINE_AA=16,
            putText=lambda *args: calls.append(("putText", args)),
            rectangle=lambda *args: calls.append(("rectangle", args)),
            circle=lambda *args: calls.append(("circle", args)),
            line=lambda *args: calls.append(("line", args)),
            imshow=lambda *args: calls.append(("imshow", args)),
            waitKey=lambda _delay: -1,
        )
        original_cv2 = sys.modules.get("cv2")
        sys.modules["cv2"] = fake_cv2
        try:
            landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
            landmarks[4] = (0.25, 0.50, 0.0)
            landmarks[8] = (0.75, 0.50, 0.0)
            hand_frame = HandFrame(
                timestamp_ms=1,
                image_width=640,
                image_height=480,
                landmarks_img=tuple(landmarks),
                landmarks_world=tuple((0.0, 0.0, 0.0) for _ in range(21)),
                handedness="Right",
                detection_confidence=0.9,
                presence_confidence=0.9,
                tracking_confidence=0.9,
            )

            OpenCVPreviewRenderer().render(
                _Frame(),
                None,
                commands=[
                    ActionCommand.left_click(timestamp_ms=1, source_state="ClickCommitted")
                ],
                results=(),
                backend="dry_run",
                dry_run=True,
                hand_frame=hand_frame,
                stats=PreviewStats(
                    frames_read=30,
                    hand_frames=29,
                    commands_emitted=8,
                    dispatches=8,
                    failures=0,
                    fps=28.5,
                    cursor_update_hz=24.0,
                    move_gap_p95_ms=45.0,
                    movement_coverage=0.82,
                    frame_drops=2,
                    stale_frames=3,
                    calibration_status="calibrated",
                ),
            )
        finally:
            if original_cv2 is None:
                sys.modules.pop("cv2", None)
            else:
                sys.modules["cv2"] = original_cv2

        rendered_text = " ".join(
            args[1] for name, args in calls if name == "putText" and isinstance(args[1], str)
        )
        self.assertIn("fps=28.5", rendered_text)
        self.assertIn("frames=30", rendered_text)
        self.assertIn("hands=29", rendered_text)
        self.assertIn("cursor_hz=24.0", rendered_text)
        self.assertIn("gap_p95=45.0ms", rendered_text)
        self.assertIn("coverage=82%", rendered_text)
        self.assertIn("drops=2", rendered_text)
        self.assertIn("stale=3", rendered_text)
        self.assertIn("calibration=calibrated", rendered_text)
        self.assertIn("ACTION left_click", rendered_text)
        self.assertTrue(any(name == "rectangle" for name, _args in calls))
        self.assertTrue(
            any(
                name == "line"
                and args[1] == (160, 240)
                and args[2] == (480, 240)
                and args[3] == (255, 0, 255)
                for name, args in calls
            )
        )


if __name__ == "__main__":
    unittest.main()
