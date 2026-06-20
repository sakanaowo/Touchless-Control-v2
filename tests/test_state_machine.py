import unittest
from dataclasses import replace

from tests.test_primitives import _feature
from touchless_control.contracts import PrimitiveEvent


def _event(event_type: str, timestamp_ms: int = 100, **source_features) -> PrimitiveEvent:
    return PrimitiveEvent(
        timestamp_ms=timestamp_ms,
        type=event_type,
        confidence=0.95,
        source_features=source_features,
    )


class InteractionStateMachineTests(unittest.TestCase):
    def test_no_hand_enters_pointing_after_stable_pointing(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        outputs = machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])

        self.assertEqual(machine.state, "Pointing")
        self.assertEqual(outputs[0].new_state, "Pointing")

    def test_pointing_enters_paused_on_open_palm(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        outputs = machine.step(_feature(timestamp_ms=2, open_palm=True), [_event("open_palm", 2)])

        self.assertEqual(machine.state, "Paused")
        self.assertEqual(outputs[0].new_state, "Paused")

    def test_short_pinch_release_commits_left_click_and_cooldown(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        machine.step(
            _feature(timestamp_ms=10, pinch_center_norm=(0.4, 0.4)),
            [_event("pinch_closed", 10)],
        )
        outputs = machine.step(
            _feature(timestamp_ms=120, pinch_center_norm=(0.405, 0.405)),
            [_event("pinch_opened", 120)],
        )
        commands = [output for output in outputs if getattr(output, "type", None) == "left_click"]

        self.assertEqual(machine.state, "Cooldown")
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].source_state, "ClickCommitted")

    def test_held_pinch_enters_dragging_and_releases_on_tracking_loss(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        machine.step(
            _feature(timestamp_ms=10, pinch_center_norm=(0.4, 0.4)),
            [_event("pinch_closed", 10)],
        )
        drag_outputs = machine.step(_feature(timestamp_ms=400), [])
        self.assertEqual(machine.state, "Dragging")
        self.assertIn("left_down", [getattr(output, "type", None) for output in drag_outputs])

        lost_feature = replace(_feature(timestamp_ms=450), hand_present=False, tracking_lost=True)
        lost_outputs = machine.step(lost_feature, [_event("tracking_lost", 450)])

        self.assertEqual(machine.state, "TrackingLost")
        self.assertIn("left_up", [getattr(output, "type", None) for output in lost_outputs])

    def test_two_finger_swipe_enters_scrolling_and_dispatches_wheel(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        outputs = machine.step(
            _feature(timestamp_ms=20, two_finger_ready=True),
            [_event("two_finger_swipe", 20, direction="up")],
        )
        commands = [output for output in outputs if getattr(output, "type", None) == "scroll_vertical"]

        self.assertEqual(machine.state, "Scrolling")
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].wheel_delta, 120)


if __name__ == "__main__":
    unittest.main()
