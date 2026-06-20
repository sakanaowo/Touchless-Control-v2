import unittest


class LandmarkFixtureTests(unittest.TestCase):
    def test_stable_pointing_fixture_has_21_landmarks(self) -> None:
        from tests.fixtures.landmarks import stable_pointing_hand

        frame = stable_pointing_hand(timestamp_ms=42)

        self.assertEqual(frame.timestamp_ms, 42)
        self.assertEqual(len(frame.landmarks_img), 21)
        self.assertEqual(len(frame.landmarks_world), 21)
        self.assertEqual(frame.handedness, "right")

    def test_tracking_lost_fixture_marks_low_confidence(self) -> None:
        from tests.fixtures.landmarks import tracking_lost_hand

        frame = tracking_lost_hand(timestamp_ms=99)

        self.assertLess(frame.tracking_confidence, 0.5)
        self.assertLess(frame.presence_confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
