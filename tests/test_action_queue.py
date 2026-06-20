import unittest

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


class ActionQueueTests(unittest.TestCase):
    def test_ignores_none_commands(self) -> None:
        from touchless_control.control import ActionQueue

        queue = ActionQueue()
        queue.enqueue(ActionCommand.none(timestamp_ms=1, source_state="Pointing"))

        self.assertEqual(queue.pending_count, 0)

    def test_coalesces_stale_relative_movement_to_latest_command(self) -> None:
        from touchless_control.control import ActionQueue

        queue = ActionQueue()
        queue.enqueue(ActionCommand.move_relative(timestamp_ms=1, dx_px=1, dy_px=1, source_state="Pointing"))
        queue.enqueue(ActionCommand.move_relative(timestamp_ms=2, dx_px=5, dy_px=-3, source_state="Pointing"))
        controller = _Controller()

        queue.flush(controller)

        self.assertEqual(len(controller.commands), 1)
        self.assertEqual(controller.commands[0].dx_px, 5)
        self.assertEqual(controller.commands[0].dy_px, -3)

    def test_preserves_button_command_order(self) -> None:
        from touchless_control.control import ActionQueue

        queue = ActionQueue()
        queue.enqueue(ActionCommand.left_down(timestamp_ms=1, source_state="Dragging"))
        queue.enqueue(ActionCommand.left_up(timestamp_ms=2, source_state="Dragging"))
        controller = _Controller()

        queue.flush(controller)

        self.assertEqual([command.type for command in controller.commands], ["left_down", "left_up"])

    def test_safe_release_enqueues_left_up_only_when_button_is_down(self) -> None:
        from touchless_control.control import ActionQueue

        queue = ActionQueue()
        queue.safe_release(timestamp_ms=1, source_state="TrackingLost")
        self.assertEqual(queue.pending_count, 0)

        queue.enqueue(ActionCommand.left_down(timestamp_ms=2, source_state="Dragging"))
        queue.safe_release(timestamp_ms=3, source_state="TrackingLost")
        controller = _Controller()
        queue.flush(controller)

        self.assertEqual([command.type for command in controller.commands], ["left_down", "left_up"])


if __name__ == "__main__":
    unittest.main()
