import unittest

from touchless_control.contracts import ActionCommand


class _Recorder:
    def __init__(self) -> None:
        self.payloads = []

    def __call__(self, payload) -> None:
        self.payloads.append(payload)


class MouseControllerTests(unittest.TestCase):
    def test_windows_controller_dispatches_relative_move_payload(self) -> None:
        from touchless_control.control import WindowsMouseController

        recorder = _Recorder()
        controller = WindowsMouseController(sender=recorder)
        result = controller.dispatch(
            ActionCommand.move_relative(
                timestamp_ms=10,
                dx_px=3,
                dy_px=-2,
                source_state="Pointing",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.backend, "windows_sendinput")
        self.assertEqual(recorder.payloads, [{"kind": "move", "dx": 3, "dy": -2}])

    def test_windows_controller_expands_left_click_to_down_up_payloads(self) -> None:
        from touchless_control.control import WindowsMouseController

        recorder = _Recorder()
        controller = WindowsMouseController(sender=recorder)

        controller.dispatch(ActionCommand.left_click(timestamp_ms=20, source_state="ClickCommitted"))

        self.assertEqual(
            recorder.payloads,
            [
                {"kind": "button", "button": "left", "pressed": True},
                {"kind": "button", "button": "left", "pressed": False},
            ],
        )

    def test_linux_controller_dispatches_uinput_style_scroll_payload(self) -> None:
        from touchless_control.control import LinuxMouseController

        recorder = _Recorder()
        controller = LinuxMouseController(writer=recorder)
        result = controller.dispatch(
            ActionCommand.scroll_vertical(
                timestamp_ms=30,
                wheel_delta=-120,
                source_state="Scrolling",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.backend, "linux_uinput")
        self.assertEqual(
            recorder.payloads,
            [{"type": "EV_REL", "code": "REL_WHEEL", "value": -120}],
        )

    def test_controller_reports_dispatch_errors_without_raising(self) -> None:
        from touchless_control.control import WindowsMouseController

        def broken_sender(_payload) -> None:
            raise RuntimeError("blocked")

        controller = WindowsMouseController(sender=broken_sender)
        result = controller.dispatch(ActionCommand.left_down(timestamp_ms=40, source_state="Dragging"))

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "RuntimeError")

    def test_factory_auto_detects_windows_controller(self) -> None:
        from touchless_control.control import WindowsMouseController, create_mouse_controller

        controller = create_mouse_controller(platform_name="Windows", sender=_Recorder())

        self.assertIsInstance(controller, WindowsMouseController)

    def test_factory_uses_real_windows_sender_when_no_sender_is_injected(self) -> None:
        from touchless_control.control import WindowsMouseController, create_mouse_controller

        controller = create_mouse_controller(platform_name="Windows")

        self.assertIsInstance(controller, WindowsMouseController)

    def test_sendinput_sender_calls_windows_api_boundary(self) -> None:
        from touchless_control.control.os.windows import create_sendinput_sender

        calls = []

        def fake_send_input(count, input_pointer, input_size):
            calls.append((count, input_pointer, input_size))
            return count

        sender = create_sendinput_sender(send_input=fake_send_input)
        sender({"kind": "move", "dx": 4, "dy": -3})

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 1)
        self.assertGreater(calls[0][2], 0)

    def test_sendinput_sender_raises_when_windows_reports_partial_send(self) -> None:
        from touchless_control.control.os.windows import create_sendinput_sender

        sender = create_sendinput_sender(send_input=lambda _count, _input_pointer, _input_size: 0)

        with self.assertRaises(OSError):
            sender({"kind": "button", "button": "left", "pressed": True})

    def test_sendinput_sender_reuses_windows_api_for_high_rate_move_burst(self) -> None:
        from touchless_control.control.os.windows import create_sendinput_sender

        factory_calls = []
        api_calls = []

        def fake_api(count, input_pointer, input_size):
            api_calls.append((count, input_pointer, input_size))
            return count

        def fake_factory():
            factory_calls.append(True)
            return fake_api

        sender = create_sendinput_sender(send_input_factory=fake_factory)
        for _index in range(120):
            sender({"kind": "move", "dx": 2, "dy": -1})

        self.assertEqual(len(factory_calls), 1)
        self.assertEqual(len(api_calls), 120)

    def test_factory_auto_detects_linux_controller(self) -> None:
        from touchless_control.control import LinuxMouseController, create_mouse_controller

        controller = create_mouse_controller(platform_name="Linux", writer=_Recorder())

        self.assertIsInstance(controller, LinuxMouseController)

    def test_factory_rejects_unsupported_operating_system(self) -> None:
        from touchless_control.control import create_mouse_controller

        with self.assertRaises(ValueError):
            create_mouse_controller(platform_name="Darwin", sender=_Recorder())


if __name__ == "__main__":
    unittest.main()
