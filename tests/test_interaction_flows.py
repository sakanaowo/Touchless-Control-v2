import unittest
from dataclasses import replace

from tests.test_primitives import _feature
from tests.test_state_machine import _event
from touchless_control.control import ActionQueue
from touchless_control.contracts import ActionCommand, OSDispatchResult


class _Controller:
    backend_name = "test"

    def __init__(self) -> None:
        self.commands = []

    def dispatch(self, command: ActionCommand) -> OSDispatchResult:
        self.commands.append(command)
        return OSDispatchResult(
            timestamp_ms=command.timestamp_ms,
            command_type=command.type,
            success=True,
            backend=self.backend_name,
            error_code=None,
            dispatch_latency_ms=0.0,
        )


def _commands(outputs):
    return [output for output in outputs if isinstance(output, ActionCommand)]


class InteractionFlowTests(unittest.TestCase):
    def test_feature_sequence_commits_click_action_through_queue(self) -> None:
        from touchless_control.interaction import InteractionStateMachine, PrimitiveDetector

        detector = PrimitiveDetector()
        machine = InteractionStateMachine()
        queue = ActionQueue()
        controller = _Controller()

        for feature in (
            _feature(timestamp_ms=1),
            _feature(timestamp_ms=20, pinch_ratio=0.29, pinch_center_norm=(0.40, 0.45)),
            _feature(timestamp_ms=120, pinch_ratio=0.46, pinch_center_norm=(0.405, 0.452)),
        ):
            for command in _commands(machine.step(feature, detector.detect(feature))):
                queue.enqueue(command)

        queue.flush(controller)

        self.assertEqual([command.type for command in controller.commands], ["left_click"])

    def test_feature_sequence_dispatches_drag_down_move_and_up(self) -> None:
        from touchless_control.control import CursorMapper
        from touchless_control.interaction import InteractionStateMachine, PrimitiveDetector

        detector = PrimitiveDetector()
        machine = InteractionStateMachine()
        mapper = CursorMapper(source_state="Dragging")
        queue = ActionQueue()
        controller = _Controller()

        for feature in (
            _feature(timestamp_ms=1),
            _feature(timestamp_ms=20, pinch_ratio=0.29, pinch_center_norm=(0.40, 0.45)),
            _feature(timestamp_ms=320, pinch_ratio=0.29, pinch_center_norm=(0.40, 0.45)),
        ):
            for command in _commands(machine.step(feature, detector.detect(feature))):
                queue.enqueue(command)

        queue.enqueue(mapper.map_motion(_feature(timestamp_ms=340, hand_velocity_norm=(0.05, 0.0))))
        release = _feature(timestamp_ms=380, pinch_ratio=0.46, pinch_center_norm=(0.45, 0.45))
        for command in _commands(machine.step(release, detector.detect(release))):
            queue.enqueue(command)
        queue.flush(controller)

        self.assertEqual(
            [command.type for command in controller.commands],
            ["left_down", "move_relative", "left_up"],
        )

    def test_scroll_sequence_dispatches_bounded_wheel_commands(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        enter = machine.step(
            _feature(timestamp_ms=20, two_finger_ready=True),
            [_event("two_finger_swipe", 20, direction="up")],
        )
        repeat = machine.step(
            _feature(timestamp_ms=140, two_finger_ready=True),
            [_event("two_finger_swipe", 140, direction="down")],
        )

        commands = _commands(enter + repeat)

        self.assertEqual([command.type for command in commands], ["scroll_vertical", "scroll_vertical"])
        self.assertEqual([command.wheel_delta for command in commands], [120, -120])

    def test_scroll_sequence_rate_limits_repeated_wheel_commands(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        enter = machine.step(
            _feature(timestamp_ms=20, two_finger_ready=True),
            [_event("two_finger_swipe", 20, direction="up")],
        )
        too_soon = machine.step(
            _feature(timestamp_ms=70, two_finger_ready=True),
            [_event("two_finger_swipe", 70, direction="up")],
        )
        after_interval = machine.step(
            _feature(timestamp_ms=121, two_finger_ready=True),
            [_event("two_finger_swipe", 121, direction="up")],
        )

        self.assertEqual(len(_commands(enter)), 1)
        self.assertEqual(_commands(too_soon), [])
        self.assertEqual(len(_commands(after_interval)), 1)

    def test_tracking_loss_sequence_has_no_accidental_click_and_safe_release_if_dragging(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        machine.step(_feature(timestamp_ms=20), [_event("pinch_closed", 20)])
        machine.step(_feature(timestamp_ms=320), [])
        lost_feature = replace(_feature(timestamp_ms=340), hand_present=False, tracking_lost=True)
        outputs = machine.step(lost_feature, [_event("tracking_lost", 340)])
        command_types = [command.type for command in _commands(outputs)]

        self.assertEqual(command_types, ["left_up"])
        self.assertNotIn("left_click", command_types)

    def test_paused_sequence_blocks_click_drag_scroll_and_movement_dispatch(self) -> None:
        from touchless_control.interaction import InteractionStateMachine

        machine = InteractionStateMachine()
        machine.step(_feature(timestamp_ms=1), [_event("pointing", 1)])
        machine.step(_feature(timestamp_ms=2, open_palm=True), [_event("open_palm", 2)])
        outputs = machine.step(
            _feature(timestamp_ms=3, open_palm=True, two_finger_ready=True),
            [
                _event("open_palm", 3),
                _event("pinch_closed", 3),
                _event("two_finger_swipe", 3, direction="up"),
            ],
        )

        self.assertEqual(machine.state, "Paused")
        self.assertEqual(_commands(outputs), [])


if __name__ == "__main__":
    unittest.main()
