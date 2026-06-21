import unittest

from touchless_control.contracts import ActionCommand, OSDispatchResult


class _Capture:
    def __init__(self, frames):
        self.frames = list(frames)
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        if not self.frames:
            return False, None
        return True, self.frames.pop(0)

    def release(self):
        self.released = True


class _Perception:
    def __init__(self, hand_frames):
        self.hand_frames = list(hand_frames)
        self.submitted = []

    def submit(self, frame, timestamp_ms):
        self.submitted.append((frame, timestamp_ms))

    def poll_latest(self):
        if not self.hand_frames:
            return None
        return self.hand_frames.pop(0)


class _Normalizer:
    def __init__(self, feature):
        self.feature = feature
        self.inputs = []

    def to_features(self, hand_frame):
        self.inputs.append(hand_frame)
        return self.feature


class _Pipeline:
    def __init__(self, command, *, primitive_events=(), interaction_events=()):
        self.command = command
        self.features = []
        self.pending = []
        self.last_primitive_events = tuple(primitive_events)
        self.last_interaction_events = tuple(interaction_events)

    def step(self, feature_frame):
        self.features.append(feature_frame)
        self.pending.append(self.command)
        return (self.command,)

    def flush(self, controller):
        results = []
        while self.pending:
            results.append(controller.dispatch(self.pending.pop(0)))
        return results


class _Controller:
    backend_name = "test"

    def __init__(self):
        self.commands = []

    def dispatch(self, command):
        self.commands.append(command)
        return OSDispatchResult(
            timestamp_ms=command.timestamp_ms,
            command_type=command.type,
            success=True,
            backend=self.backend_name,
            error_code=None,
            dispatch_latency_ms=0.0,
        )


class _PreviewRenderer:
    def __init__(self, quit_after: int | None = None):
        self.frames = []
        self.closed = False
        self.quit_after = quit_after

    def render(
        self,
        frame,
        snapshot,
        *,
        commands,
        results,
        backend,
        dry_run,
        hand_frame=None,
        stats=None,
    ):
        self.frames.append(
            (
                frame,
                snapshot,
                tuple(commands),
                tuple(results),
                backend,
                dry_run,
                hand_frame,
                stats,
            )
        )
        return self.quit_after is not None and len(self.frames) >= self.quit_after

    def close(self):
        self.closed = True


class LiveRunnerTests(unittest.TestCase):
    def test_live_runner_processes_hand_frames_and_dispatches_pipeline_commands(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame"])
        perception = _Perception(hand_frames=["hand"])
        feature = _feature(timestamp_ms=10, hand_velocity_norm=(0.05, 0.0))
        normalizer = _Normalizer(feature)
        command = ActionCommand.move_relative(
            timestamp_ms=10,
            dx_px=4,
            dy_px=0,
            source_state="Pointing",
        )
        controller = _Controller()
        pipeline = _Pipeline(command)

        runner = LiveRunner(
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: f"converted:{frame}",
            timestamp_ms=lambda: 10,
            normalizer=normalizer,
            pipeline=pipeline,
            controller_factory=lambda: controller,
        )

        result = runner.run(max_frames=1)

        self.assertTrue(result.success)
        self.assertTrue(capture.released)
        self.assertEqual(perception.submitted, [("converted:frame", 10)])
        self.assertEqual(normalizer.inputs, ["hand"])
        self.assertEqual(pipeline.features, [feature])
        self.assertEqual(controller.commands, [command])
        self.assertEqual(result.frames_read, 1)
        self.assertEqual(result.hand_frames, 1)
        self.assertEqual(result.commands_emitted, 1)
        self.assertEqual(result.dispatches, 1)
        self.assertEqual(result.failures, 0)
        self.assertEqual(result.backend, "test")
        self.assertEqual(result.log_records, 1)
        self.assertEqual(result.p95_latency_ms, 0.0)

    def test_live_runner_waits_briefly_for_async_perception_result(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame"])
        perception = _Perception(hand_frames=[None, "hand"])
        normalizer = _Normalizer(_feature(timestamp_ms=10))
        command = ActionCommand.move_relative(
            timestamp_ms=10,
            dx_px=4,
            dy_px=0,
            source_state="Pointing",
        )
        sleeps = []

        runner = LiveRunner(
            dry_run=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 10,
            normalizer=normalizer,
            pipeline=_Pipeline(command),
            poll_timeout_ms=5,
            poll_interval_ms=1,
            sleep_ms=sleeps.append,
        )

        result = runner.run(max_frames=1)

        self.assertEqual(result.hand_frames, 1)
        self.assertEqual(result.commands_emitted, 1)
        self.assertEqual(sleeps, [1])

    def test_live_runner_dry_run_does_not_create_real_controller(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame"])
        perception = _Perception(hand_frames=["hand"])
        command = ActionCommand.left_click(timestamp_ms=20, source_state="ClickCommitted")

        def real_controller_factory():
            raise AssertionError("real controller should not be created in dry-run")

        runner = LiveRunner(
            dry_run=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 20,
            normalizer=_Normalizer(_feature(timestamp_ms=20)),
            pipeline=_Pipeline(command),
            controller_factory=real_controller_factory,
        )

        result = runner.run(max_frames=1)

        self.assertTrue(result.success)
        self.assertEqual(result.commands_emitted, 1)
        self.assertEqual(result.dispatches, 1)
        self.assertEqual(result.failures, 0)
        self.assertEqual(result.backend, "dry_run")

    def test_live_runner_writes_jsonl_session_log_when_path_is_configured(self):
        from tests.test_primitives import _feature
        from touchless_control.contracts import InteractionEvent, PrimitiveEvent
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame"])
        perception = _Perception(hand_frames=["hand"])
        command = ActionCommand.left_click(timestamp_ms=20, source_state="ClickCommitted")
        writes = []

        runner = LiveRunner(
            dry_run=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 20,
            normalizer=_Normalizer(_feature(timestamp_ms=20, pinch_ratio=0.29)),
            pipeline=_Pipeline(
                command,
                primitive_events=[
                    PrimitiveEvent(
                        timestamp_ms=20,
                        type="pinch_closed",
                        confidence=0.95,
                        source_features={"pinch_ratio": 0.29},
                    )
                ],
                interaction_events=[
                    InteractionEvent(
                        timestamp_ms=20,
                        prev_state="Pointing",
                        new_state="ClickCandidate",
                        reason="pinch_closed",
                        confidence=0.95,
                        elapsed_in_prev_state_ms=10,
                    )
                ],
            ),
            log_path="C:/tmp/touchless-session.jsonl",
            log_writer=lambda path, content: writes.append((path, content)),
        )

        result = runner.run(max_frames=1)

        self.assertTrue(result.success)
        self.assertEqual(result.log_path, "C:/tmp/touchless-session.jsonl")
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], "C:/tmp/touchless-session.jsonl")
        self.assertIn('"primitive_types": ["pinch_closed"]', writes[0][1])
        self.assertIn('"interaction_reasons": ["pinch_closed"]', writes[0][1])
        self.assertIn('"action_types": ["left_click"]', writes[0][1])
        self.assertIn('"pinch_ratio": 0.29', writes[0][1])

    def test_live_runner_preview_renders_observable_state_for_hand_frames(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame"])
        perception = _Perception(hand_frames=["hand"])
        command = ActionCommand.move_relative(
            timestamp_ms=10,
            dx_px=4,
            dy_px=0,
            source_state="Pointing",
        )
        preview = _PreviewRenderer()

        runner = LiveRunner(
            dry_run=True,
            preview=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 10,
            normalizer=_Normalizer(_feature(timestamp_ms=10, pinch_ratio=0.31)),
            pipeline=_Pipeline(command),
            preview_renderer=preview,
        )

        result = runner.run(max_frames=1)

        self.assertTrue(result.success)
        self.assertTrue(preview.closed)
        self.assertEqual(result.preview_frames, 1)
        frame, snapshot, commands, results, backend, dry_run, hand_frame, stats = preview.frames[0]
        self.assertEqual(frame, "frame")
        self.assertEqual(hand_frame, "hand")
        self.assertEqual(stats.frames_read, 1)
        self.assertEqual(stats.hand_frames, 1)
        self.assertEqual(stats.commands_emitted, 1)
        self.assertEqual(stats.dispatches, 1)
        self.assertEqual(stats.failures, 0)
        self.assertEqual(snapshot.state, "Pointing")
        self.assertEqual(snapshot.tracking_status, "stable")
        self.assertEqual(commands[0].type, "move_relative")
        self.assertEqual(results[0].backend, "dry_run")
        self.assertEqual(backend, "dry_run")
        self.assertTrue(dry_run)

    def test_live_runner_preview_can_stop_live_loop(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame-1", "frame-2"])
        perception = _Perception(hand_frames=["hand-1", "hand-2"])
        preview = _PreviewRenderer(quit_after=1)

        runner = LiveRunner(
            dry_run=True,
            preview=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 10,
            normalizer=_Normalizer(_feature(timestamp_ms=10)),
            pipeline=_Pipeline(ActionCommand.left_click(timestamp_ms=10, source_state="ClickCommitted")),
            preview_renderer=preview,
        )

        result = runner.run(max_frames=2)

        self.assertEqual(result.frames_read, 1)
        self.assertEqual(result.preview_frames, 1)


if __name__ == "__main__":
    unittest.main()
