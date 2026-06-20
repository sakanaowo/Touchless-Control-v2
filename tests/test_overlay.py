import unittest
from dataclasses import replace

from tests.test_primitives import _feature


class OverlayPresenterTests(unittest.TestCase):
    def test_reports_current_state_and_active_mode(self) -> None:
        from touchless_control.presentation import OverlayPresenter

        snapshot = OverlayPresenter().snapshot(
            feature_frame=_feature(),
            state="Scrolling",
            latency_ms=42.0,
        )

        self.assertEqual(snapshot.state, "Scrolling")
        self.assertEqual(snapshot.active_mode, "scroll")
        self.assertEqual(snapshot.tracking_status, "stable")
        self.assertFalse(snapshot.high_latency)

    def test_warns_when_latency_exceeds_budget(self) -> None:
        from touchless_control.presentation import OverlayPresenter

        snapshot = OverlayPresenter(latency_warning_ms=80.0).snapshot(
            feature_frame=_feature(),
            state="Pointing",
            latency_ms=84.5,
        )

        self.assertTrue(snapshot.high_latency)
        self.assertEqual(snapshot.message, "latency_warning")

    def test_reports_tracking_lost_status(self) -> None:
        from touchless_control.presentation import OverlayPresenter

        lost_feature = replace(_feature(), hand_present=False, tracking_lost=True)
        snapshot = OverlayPresenter().snapshot(
            feature_frame=lost_feature,
            state="TrackingLost",
            latency_ms=None,
        )

        self.assertEqual(snapshot.tracking_status, "tracking_lost")
        self.assertEqual(snapshot.active_mode, "tracking_lost")
        self.assertEqual(snapshot.latency_ms, None)


if __name__ == "__main__":
    unittest.main()
