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


class _ConfigurableCapture(_Capture):
    def __init__(self, frames):
        super().__init__(frames)
        self.properties = []

    def set(self, property_id, value):
        self.properties.append((property_id, value))
        return True


class _FlakyCapture:
    def __init__(self, reads):
        self.reads = list(reads)
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        if not self.reads:
            return False, None
        return self.reads.pop(0)

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


class _StickyPerception:
    def __init__(self, hand_frame):
        self.hand_frame = hand_frame
        self.submitted = []

    def submit(self, frame, timestamp_ms):
        self.submitted.append((frame, timestamp_ms))

    def poll_latest(self):
        return self.hand_frame


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

    def test_live_preview_receives_runtime_pointer_diagnostics(self):
        from types import SimpleNamespace

        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        features = iter(
            [
                _feature(timestamp_ms=100, hand_velocity_norm=(0.02, 0.0)),
                _feature(timestamp_ms=140, hand_velocity_norm=(0.02, 0.0)),
                _feature(timestamp_ms=180, hand_velocity_norm=(0.02, 0.0)),
            ]
        )
        preview = _PreviewRenderer()
        runner = LiveRunner(
            dry_run=True,
            preview=True,
            capture_factory=lambda _index: _Capture(frames=["a", "b", "c"]),
            perception_factory=lambda _width, _height: _Perception(
                hand_frames=["ha", "hb", "hc"]
            ),
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 100,
            normalizer=SimpleNamespace(to_features=lambda _hand: next(features)),
            pipeline=_Pipeline(
                ActionCommand.move_relative(
                    timestamp_ms=100,
                    dx_px=2,
                    dy_px=0,
                    source_state="Pointing",
                )
            ),
            preview_renderer=preview,
            calibration_status="calibrated",
        )

        runner.run(max_frames=3)

        stats = preview.frames[-1][-1]
        self.assertEqual(stats.cursor_update_hz, 37.5)
        self.assertEqual(stats.move_gap_p95_ms, 40.0)
        self.assertEqual(stats.movement_coverage, 1.0)
        self.assertEqual(stats.frame_drops, 0)
        self.assertEqual(stats.stale_frames, 0)
        self.assertEqual(stats.calibration_status, "calibrated")

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

    def test_live_runner_tolerates_transient_camera_read_failures(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _FlakyCapture(reads=[(False, None), (True, "frame")])
        perception = _Perception(hand_frames=["hand"])
        command = ActionCommand.left_click(timestamp_ms=10, source_state="ClickCommitted")

        runner = LiveRunner(
            dry_run=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 10,
            normalizer=_Normalizer(_feature(timestamp_ms=10)),
            pipeline=_Pipeline(command),
            max_read_failures=2,
        )

        result = runner.run(max_frames=1)

        self.assertTrue(result.success)
        self.assertEqual(result.frames_read, 1)
        self.assertEqual(result.read_failures, 1)
        self.assertEqual(result.error_code, None)

    def test_live_runner_default_pipeline_uses_responsive_inverted_cursor(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame"])
        perception = _Perception(hand_frames=["hand"])
        controller = _Controller()

        runner = LiveRunner(
            camera_index=0,
            dry_run=False,
            preset_name="responsive",
            invert_x=True,
            cursor_gain_scale=1.25,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: perception,
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 10,
            normalizer=_Normalizer(
                _feature(timestamp_ms=10, hand_velocity_norm=(0.012, 0.0))
            ),
            controller_factory=lambda: controller,
        )

        result = runner.run(max_frames=1)

        self.assertEqual(result.commands_emitted, 1)
        self.assertEqual(controller.commands[0].type, "move_relative")
        self.assertLess(controller.commands[0].dx_px, 0)

    def test_live_runner_configures_camera_for_low_latency_capture(self):
        from touchless_control.runtime.live import LiveRunner

        capture = _ConfigurableCapture(frames=[])

        runner = LiveRunner(
            dry_run=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: _Perception([]),
            image_width=640,
            image_height=480,
            camera_fps=60,
            camera_buffer_size=1,
            max_read_failures=1,
        )

        runner.run(max_frames=1)

        self.assertEqual(
            capture.properties[:4],
            [(3, 640), (4, 480), (5, 60), (38, 1)],
        )

    def test_live_runner_skips_stale_hand_frames(self):
        from tests.test_primitives import _feature
        from touchless_control.runtime.live import LiveRunner

        capture = _Capture(frames=["frame-1", "frame-2"])
        feature = _feature(timestamp_ms=10, hand_velocity_norm=(0.02, 0.0))
        command = ActionCommand.move_relative(
            timestamp_ms=10,
            dx_px=4,
            dy_px=0,
            source_state="Pointing",
        )
        pipeline = _Pipeline(command)

        runner = LiveRunner(
            dry_run=True,
            capture_factory=lambda _index: capture,
            perception_factory=lambda _width, _height: _StickyPerception("same-hand"),
            frame_converter=lambda frame: frame,
            timestamp_ms=lambda: 20,
            normalizer=_Normalizer(feature),
            pipeline=pipeline,
        )

        result = runner.run(max_frames=2)

        self.assertEqual(result.frames_read, 2)
        self.assertEqual(result.hand_frames, 1)
        self.assertEqual(result.commands_emitted, 1)
        self.assertEqual(pipeline.features, [feature])


if __name__ == "__main__":
    unittest.main()
