from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any

from touchless_control.control.os.base import PayloadSender, dispatch_result
from touchless_control.core.contracts import ActionCommand, OSDispatchResult

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput)]


class _Input(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _InputUnion),
    ]


@dataclass(slots=True)
class WindowsMouseController:
    sender: PayloadSender
    backend_name: str = "windows_sendinput"

    def dispatch(self, command: ActionCommand) -> OSDispatchResult:
        try:
            for payload in _windows_payloads(command):
                self.sender(payload)
        except Exception as error:
            return dispatch_result(command, self.backend_name, False, type(error).__name__)
        return dispatch_result(command, self.backend_name, True, None)


def create_sendinput_sender(
    send_input: Any | None = None,
    *,
    send_input_factory: Any | None = None,
) -> PayloadSender:
    api = send_input
    api_factory = send_input_factory or _create_send_input_api

    def sender(payload: dict[str, Any]) -> None:
        nonlocal api
        if api is None:
            api = api_factory()
        mouse_input = _payload_to_input(payload)
        inputs = (_Input * 1)(mouse_input)
        sent_count = api(1, inputs, ctypes.sizeof(_Input))
        if sent_count != 1:
            raise OSError("SendInput failed")

    return sender


def _windows_payloads(command: ActionCommand) -> list[dict[str, Any]]:
    if command.type == "move_relative":
        return [{"kind": "move", "dx": command.dx_px or 0, "dy": command.dy_px or 0}]
    if command.type == "left_down":
        return [{"kind": "button", "button": "left", "pressed": True}]
    if command.type == "left_up":
        return [{"kind": "button", "button": "left", "pressed": False}]
    if command.type == "left_click":
        return [
            {"kind": "button", "button": "left", "pressed": True},
            {"kind": "button", "button": "left", "pressed": False},
        ]
    if command.type == "scroll_vertical":
        return [{"kind": "wheel", "delta": command.wheel_delta or 0}]
    return []


def _payload_to_input(payload: dict[str, Any]) -> _Input:
    mouse_input = _MouseInput()
    if payload.get("kind") == "move":
        mouse_input.dx = int(payload.get("dx") or 0)
        mouse_input.dy = int(payload.get("dy") or 0)
        mouse_input.dwFlags = MOUSEEVENTF_MOVE
    elif payload.get("kind") == "button" and payload.get("button") == "left":
        mouse_input.dwFlags = MOUSEEVENTF_LEFTDOWN if payload.get("pressed") else MOUSEEVENTF_LEFTUP
    elif payload.get("kind") == "wheel":
        mouse_input.mouseData = ctypes.c_ulong(int(payload.get("delta") or 0)).value
        mouse_input.dwFlags = MOUSEEVENTF_WHEEL
    else:
        raise ValueError(f"Unsupported Windows input payload: {payload!r}")

    return _Input(type=INPUT_MOUSE, union=_InputUnion(mi=mouse_input))


def _create_send_input_api() -> Any:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    send_input = user32.SendInput
    send_input.argtypes = (ctypes.c_uint, ctypes.POINTER(_Input), ctypes.c_int)
    send_input.restype = ctypes.c_uint
    return send_input
