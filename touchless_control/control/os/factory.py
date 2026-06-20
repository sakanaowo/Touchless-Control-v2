from __future__ import annotations

import platform

from touchless_control.control.os.base import MouseController, PayloadSender
from touchless_control.control.os.linux import LinuxMouseController
from touchless_control.control.os.windows import WindowsMouseController, create_sendinput_sender


def create_mouse_controller(
    *,
    platform_name: str | None = None,
    sender: PayloadSender | None = None,
    writer: PayloadSender | None = None,
) -> MouseController:
    system_name = (platform_name or platform.system()).lower()
    if system_name.startswith("win"):
        if sender is None:
            sender = create_sendinput_sender()
        return WindowsMouseController(sender=sender)
    if system_name.startswith("linux"):
        if writer is None:
            raise ValueError("Linux mouse controller requires a writer")
        return LinuxMouseController(writer=writer)
    raise ValueError(f"Unsupported operating system: {platform_name or platform.system()}")
