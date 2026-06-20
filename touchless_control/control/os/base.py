from __future__ import annotations

from typing import Any, Callable, Protocol

from touchless_control.core.contracts import ActionCommand, OSDispatchResult

PayloadSender = Callable[[Any], None]


class MouseController(Protocol):
    backend_name: str

    def dispatch(self, command: ActionCommand) -> OSDispatchResult:
        ...


def dispatch_result(
    command: ActionCommand,
    backend: str,
    success: bool,
    error_code: str | None,
) -> OSDispatchResult:
    return OSDispatchResult(
        timestamp_ms=command.timestamp_ms,
        command_type=command.type,
        success=success,
        backend=backend,
        error_code=error_code,
        dispatch_latency_ms=0.0,
    )
