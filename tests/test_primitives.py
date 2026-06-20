import unittest
from dataclasses import replace

from touchless_control.contracts import FeatureFrame


def _feature(**overrides) -> FeatureFrame:
    base = FeatureFrame(
        timestamp_ms=100,
        hand_present=True,
        stability_score=0.95,
        palm_scale=0.5,
        palm_center_norm=(0.4, 0.5),
        index_tip_norm=(0.5, 0.4),
        thumb_tip_norm=(0.3, 0.5),
        middle_tip_norm=(0.52, 0.4),
        index_direction=(0.0, -1.0),
        hand_velocity_norm=(0.0, 0.0),
        pinch_ratio=0.60,
        pinch_center_norm=(0.4, 0.45),
        finger_count=1,
        two_finger_ready=False,
        open_palm=False,
        tracking_lost=False,
    )
    return replace(base, **overrides)


class PrimitiveDetectorTests(unittest.TestCase):
    def test_detects_pointing_for_stable_present_hand(self) -> None:
        from touchless_control.interaction import PrimitiveDetector

        events = PrimitiveDetector().detect(_feature())

        self.assertEqual([event.type for event in events], ["pointing"])

    def test_pinch_uses_close_open_hysteresis(self) -> None:
        from touchless_control.interaction import PrimitiveDetector

        detector = PrimitiveDetector()

        closed = detector.detect(_feature(pinch_ratio=0.29, timestamp_ms=1))
        middle = detector.detect(_feature(pinch_ratio=0.35, timestamp_ms=2))
        opened = detector.detect(_feature(pinch_ratio=0.46, timestamp_ms=3))

        self.assertIn("pinch_closed", [event.type for event in closed])
        self.assertNotIn("pinch_opened", [event.type for event in middle])
        self.assertIn("pinch_opened", [event.type for event in opened])

    def test_detects_open_palm(self) -> None:
        from touchless_control.interaction import PrimitiveDetector

        events = PrimitiveDetector().detect(_feature(open_palm=True, finger_count=5))

        self.assertIn("open_palm", [event.type for event in events])

    def test_detects_two_finger_vertical_swipe_direction(self) -> None:
        from touchless_control.interaction import PrimitiveDetector

        events = PrimitiveDetector().detect(
            _feature(
                two_finger_ready=True,
                finger_count=2,
                hand_velocity_norm=(0.0, -0.06),
            )
        )
        scroll_events = [event for event in events if event.type == "two_finger_swipe"]

        self.assertEqual(len(scroll_events), 1)
        self.assertEqual(scroll_events[0].source_features["direction"], "up")

    def test_rejects_ambiguous_scroll_when_pinch_is_closed(self) -> None:
        from touchless_control.interaction import PrimitiveDetector

        events = PrimitiveDetector().detect(
            _feature(
                pinch_ratio=0.29,
                two_finger_ready=True,
                finger_count=2,
                hand_velocity_norm=(0.0, -0.08),
            )
        )

        self.assertIn("pinch_closed", [event.type for event in events])
        self.assertNotIn("two_finger_swipe", [event.type for event in events])

    def test_tracking_lost_suppresses_other_primitives(self) -> None:
        from touchless_control.interaction import PrimitiveDetector

        events = PrimitiveDetector().detect(
            _feature(
                hand_present=False,
                tracking_lost=True,
                open_palm=True,
                pinch_ratio=0.2,
            )
        )

        self.assertEqual([event.type for event in events], ["tracking_lost"])


if __name__ == "__main__":
    unittest.main()
