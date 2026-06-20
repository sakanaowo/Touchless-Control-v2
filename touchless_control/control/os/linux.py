from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from touchless_control.control.os.base import PayloadSender, dispatch_result
from touchless_control.core.contracts import ActionCommand, OSDispatchResult


@dataclass(slots=True)
class LinuxMouseController:
    writer: PayloadSender
    backend_name: str = "linux_uinput"

    def dispatch(self, command: ActionCommand) -> OSDispatchResult:
        try:
            for payload in _linux_payloads(command):
                self.writer(payload)
        except Exception as error:
            return dispatch_result(command, self.backend_name, False, type(error).__name__)
        return dispatch_result(command, self.backend_name, True, None)


def _linux_payloads(command: ActionCommand) -> list[dict[str, Any]]:
    if command.type == "move_relative":
        return [
            {"type": "EV_REL", "code": "REL_X", "value": command.dx_px or 0},
            {"type": "EV_REL", "code": "REL_Y", "value": command.dy_px or 0},
        ]
    if command.type == "left_down":
        return [{"type": "EV_KEY", "code": "BTN_LEFT", "value": 1}]
    if command.type == "left_up":
        return [{"type": "EV_KEY", "code": "BTN_LEFT", "value": 0}]
    if command.type == "left_click":
        return [
            {"type": "EV_KEY", "code": "BTN_LEFT", "value": 1},
            {"type": "EV_KEY", "code": "BTN_LEFT", "value": 0},
        ]
    if command.type == "scroll_vertical":
        return [{"type": "EV_REL", "code": "REL_WHEEL", "value": command.wheel_delta or 0}]
    return []
