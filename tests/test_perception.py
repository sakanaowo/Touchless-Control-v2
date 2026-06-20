import unittest


class _FakeDetector:
    def __init__(self) -> None:
        self.calls = []

    def detect_async(self, frame, timestamp_ms: int) -> None:
        self.calls.append((frame, timestamp_ms))


class _CapturingFactory:
    def __init__(self) -> None:
        self.config = None
        self.callback = None
        self.detector = _FakeDetector()

    def __call__(self, *, config, result_callback):
        self.config = config
        self.callback = result_callback
        return self.detector


class _Landmark:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


class _Category:
    def __init__(self, category_name: str, score: float) -> None:
        self.category_name = category_name
        self.score = score


class _Result:
    def __init__(self, landmarks, world_landmarks, handedness) -> None:
        self.hand_landmarks = [landmarks]
        self.hand_world_landmarks = [world_landmarks]
        self.handedness = [[handedness]]


class MediaPipeHandPerceptionTests(unittest.TestCase):
    def test_adapter_uses_one_hand_live_stream_configuration(self) -> None:
        from touchless_control.perception import MediaPipeHandPerception

        factory = _CapturingFactory()
        perception = MediaPipeHandPerception(detector_factory=factory)

        self.assertEqual(factory.config.num_hands, 1)
        self.assertEqual(factory.config.running_mode, "LIVE_STREAM")
        self.assertEqual(factory.config.min_detection_confidence, 0.5)
        self.assertEqual(factory.config.min_presence_confidence, 0.5)
        self.assertEqual(factory.config.min_tracking_confidence, 0.5)

        frame = object()
        perception.submit(frame, timestamp_ms=1234)

        self.assertEqual(factory.detector.calls, [(frame, 1234)])

    def test_callback_converts_latest_result_to_hand_frame(self) -> None:
        from touchless_control.perception import MediaPipeHandPerception

        factory = _CapturingFactory()
        perception = MediaPipeHandPerception(
            detector_factory=factory,
            image_width=640,
            image_height=480,
        )
        landmarks = [_Landmark(index / 20, index / 40, -0.01) for index in range(21)]
        world_landmarks = [_Landmark(index / 10, index / 30, 0.02) for index in range(21)]
        handedness = _Category("Right", 0.91)

        factory.callback(
            _Result(landmarks, world_landmarks, handedness),
            None,
            55,
        )
        hand_frame = perception.poll_latest()

        self.assertIsNotNone(hand_frame)
        self.assertEqual(hand_frame.timestamp_ms, 55)
        self.assertEqual(hand_frame.image_width, 640)
        self.assertEqual(hand_frame.image_height, 480)
        self.assertEqual(len(hand_frame.landmarks_img), 21)
        self.assertEqual(len(hand_frame.landmarks_world), 21)
        self.assertEqual(hand_frame.handedness, "right")
        self.assertAlmostEqual(hand_frame.detection_confidence, 0.91)
        self.assertAlmostEqual(hand_frame.presence_confidence, 0.91)
        self.assertAlmostEqual(hand_frame.tracking_confidence, 0.91)

    def test_callback_ignores_empty_results(self) -> None:
        from touchless_control.perception import MediaPipeHandPerception

        factory = _CapturingFactory()
        perception = MediaPipeHandPerception(detector_factory=factory)

        factory.callback(_Result([], [], _Category("Right", 0.5)), None, 10)

        self.assertIsNone(perception.poll_latest())

    def test_real_mediapipe_factory_wraps_solutions_hands_detector(self) -> None:
        from types import SimpleNamespace

        from touchless_control.perception import (
            MediaPipeHandConfig,
            create_mediapipe_detector_factory,
        )

        processed_frames = []
        callbacks = []

        class _Hands:
            def process(self, frame):
                processed_frames.append(frame)
                return SimpleNamespace(
                    multi_hand_landmarks=["image-landmarks"],
                    multi_hand_world_landmarks=["world-landmarks"],
                    multi_handedness=["handedness"],
                )

        class _HandsModule:
            @staticmethod
            def Hands(**kwargs):
                callbacks.append(kwargs)
                return _Hands()

        fake_mediapipe = SimpleNamespace(
            solutions=SimpleNamespace(hands=_HandsModule),
        )
        factory = create_mediapipe_detector_factory(
            module_loader=lambda name: fake_mediapipe,
        )
        detector = factory(
            config=MediaPipeHandConfig(num_hands=1),
            result_callback=lambda result, image, timestamp: callbacks.append(
                (result, image, timestamp)
            ),
        )

        detector.detect_async("rgb-frame", 123)

        self.assertEqual(processed_frames, ["rgb-frame"])
        self.assertEqual(callbacks[0]["max_num_hands"], 1)
        self.assertEqual(callbacks[1][0].hand_landmarks, ["image-landmarks"])
        self.assertEqual(callbacks[1][1], "rgb-frame")
        self.assertEqual(callbacks[1][2], 123)


if __name__ == "__main__":
    unittest.main()
