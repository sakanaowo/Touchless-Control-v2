from __future__ import annotations

from dataclasses import dataclass, field

from touchless_control.control.cursor import CursorMapper
from touchless_control.control.os.base import MouseController
from touchless_control.control.pointer_engine import PointerEngine
from touchless_control.control.queue import ActionQueue
from touchless_control.core.contracts import (
    ActionCommand,
    FeatureFrame,
    IntentContext,
    InteractionEvent,
    OSDispatchResult,
    PrimitiveEvent,
)
from touchless_control.intent.policy import attention_allows_input
from touchless_control.interaction import InteractionStateMachine, PrimitiveDetector


@dataclass(slots=True)
class TouchlessPipeline:
    detector: PrimitiveDetector = field(default_factory=PrimitiveDetector)
    machine: InteractionStateMachine = field(default_factory=InteractionStateMachine)
    mapper: CursorMapper = field(default_factory=CursorMapper)
    queue: ActionQueue = field(default_factory=ActionQueue)
    pointer_engine: PointerEngine | None = None
    last_primitive_events: tuple[PrimitiveEvent, ...] = ()
    last_interaction_events: tuple[InteractionEvent, ...] = ()

    @property
    def state(self) -> str:
        return self.machine.state

    def step(self, feature_frame: FeatureFrame) -> tuple[ActionCommand, ...]:
        return self.step_context(IntentContext.from_hand(feature_frame))

    def step_context(self, context: IntentContext) -> tuple[ActionCommand, ...]:
        if context.hand_features is None:
            self.last_primitive_events = ()
            self.last_interaction_events = ()
            return ()

        if _attention_blocks_input(context):
            self.last_primitive_events = ()
            self.last_interaction_events = ()
            return self._handle_attention_block(context)

        feature_frame = context.hand_features
        primitive_events = self.detector.detect(feature_frame)
        outputs = self.machine.step(feature_frame, primitive_events)
        self.last_primitive_events = tuple(primitive_events)
        self.last_interaction_events = tuple(
            output for output in outputs if isinstance(output, InteractionEvent)
        )
        commands = [output for output in outputs if isinstance(output, ActionCommand)]

        if self.machine.state in {"Pointing", "Dragging"}:
            commands.append(self._map_motion(feature_frame))

        enqueued = []
        for command in commands:
            if command.type != "none":
                self.queue.enqueue(command)
                enqueued.append(command)

        return tuple(enqueued)

    def flush(self, controller: MouseController) -> list[OSDispatchResult]:
        return self.queue.flush(controller)

    def _map_motion(self, feature_frame: FeatureFrame) -> ActionCommand:
        """Map hand motion using PointerEngine if available, else CursorMapper."""
        if self.pointer_engine is not None:
            self.pointer_engine.source_state = self.machine.state
            return self.pointer_engine.map_motion(feature_frame)
        self.mapper.source_state = self.machine.state
        return self.mapper.map_motion(feature_frame)

    def _handle_attention_block(self, context: IntentContext) -> tuple[ActionCommand, ...]:
        if self.machine.state != "Dragging":
            return ()

        command = ActionCommand.left_up(
            timestamp_ms=context.timestamp_ms,
            source_state="AttentionBlocked",
        )
        self.queue.enqueue(command)
        self.machine.state = "Cooldown"
        self.machine._state_entered_ms = context.timestamp_ms
        return (command,)


def _attention_blocks_input(context: IntentContext) -> bool:
    return not attention_allows_input(context)
