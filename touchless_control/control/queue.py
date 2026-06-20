from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from touchless_control.control.os.base import MouseController
from touchless_control.core.contracts import ActionCommand, OSDispatchResult


@dataclass(slots=True)
class ActionQueue:
    max_size: int = 64
    _commands: deque[ActionCommand] = field(default_factory=deque)
    _left_button_down: bool = False

    @property
    def pending_count(self) -> int:
        return len(self._commands)

    def enqueue(self, command: ActionCommand) -> None:
        if command.type == "none":
            return

        if command.type == "move_relative":
            self._drop_pending_moves()

        if len(self._commands) >= self.max_size:
            self._commands.popleft()

        self._commands.append(command)
        self._track_button_state(command)

    def safe_release(self, *, timestamp_ms: int, source_state: str) -> None:
        if self._left_button_down:
            self.enqueue(ActionCommand.left_up(timestamp_ms=timestamp_ms, source_state=source_state))

    def flush(self, controller: MouseController) -> list[OSDispatchResult]:
        results = []
        while self._commands:
            results.append(controller.dispatch(self._commands.popleft()))
        return results

    def _drop_pending_moves(self) -> None:
        self._commands = deque(
            command for command in self._commands if command.type != "move_relative"
        )

    def _track_button_state(self, command: ActionCommand) -> None:
        if command.type == "left_down":
            self._left_button_down = True
        elif command.type in {"left_up", "left_click"}:
            self._left_button_down = False
