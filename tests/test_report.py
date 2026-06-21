import json
import tempfile
import unittest
from pathlib import Path


class SessionReportTests(unittest.TestCase):
    def test_analyzes_jsonl_session_log_metrics_and_distributions(self) -> None:
        from touchless_control.observability import analyze_session_log

        entries = [
            {
                "timestamp_ms": 1000,
                "latency_ms": 20.0,
                "primitive_types": ["pointing"],
                "interaction_reasons": ["hand_detected"],
                "action_types": ["move_relative"],
                "dispatch_successes": [True],
                "features": {"tracking_lost": False},
            },
            {
                "timestamp_ms": 2000,
                "latency_ms": 40.0,
                "primitive_types": ["pointing", "pinch_closed"],
                "interaction_reasons": ["pinch_closed"],
                "action_types": ["left_click"],
                "dispatch_successes": [False],
                "features": {"tracking_lost": True},
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "session.jsonl"
            log_path.write_text(
                "\n".join(json.dumps(entry) for entry in entries) + "\n",
                encoding="utf-8",
            )

            report = analyze_session_log(str(log_path))

        self.assertEqual(report.total_records, 2)
        self.assertEqual(report.action_count, 2)
        self.assertEqual(report.dispatch_count, 2)
        self.assertEqual(report.failure_count, 1)
        self.assertEqual(report.tracking_loss_count, 1)
        self.assertEqual(report.p95_latency_ms, 40.0)
        self.assertEqual(report.p99_latency_ms, 40.0)
        self.assertEqual(report.primitive_counts["pointing"], 2)
        self.assertEqual(report.primitive_counts["pinch_closed"], 1)
        self.assertEqual(report.action_counts["move_relative"], 1)
        self.assertEqual(report.action_counts["left_click"], 1)
        self.assertEqual(report.move_count, 1)
        self.assertEqual(report.cursor_update_hz, 1.0)
        self.assertEqual(report.movement_coverage, 0.5)

    def test_reports_cursor_move_cadence_metrics(self) -> None:
        from touchless_control.observability import analyze_session_entries

        entries = [
            {
                "timestamp_ms": 1000,
                "latency_ms": 10.0,
                "primitive_types": ["pointing"],
                "interaction_reasons": [],
                "action_types": ["move_relative"],
                "dispatch_successes": [True],
                "features": {"tracking_lost": False},
            },
            {
                "timestamp_ms": 1040,
                "latency_ms": 10.0,
                "primitive_types": ["pointing"],
                "interaction_reasons": [],
                "action_types": [],
                "dispatch_successes": [],
                "features": {"tracking_lost": False},
            },
            {
                "timestamp_ms": 1080,
                "latency_ms": 10.0,
                "primitive_types": ["pointing"],
                "interaction_reasons": [],
                "action_types": ["move_relative"],
                "dispatch_successes": [True],
                "features": {"tracking_lost": False},
            },
            {
                "timestamp_ms": 1160,
                "latency_ms": 10.0,
                "primitive_types": ["pointing"],
                "interaction_reasons": [],
                "action_types": ["move_relative"],
                "dispatch_successes": [True],
                "features": {"tracking_lost": False},
            },
        ]

        report = analyze_session_entries(entries)

        self.assertEqual(report.move_count, 3)
        self.assertAlmostEqual(report.cursor_update_hz, 18.75)
        self.assertEqual(report.move_gap_p50_ms, 80.0)
        self.assertEqual(report.move_gap_p95_ms, 80.0)
        self.assertEqual(report.move_gap_max_ms, 80.0)
        self.assertEqual(report.movement_coverage, 0.75)

    def test_report_lines_are_cli_friendly(self) -> None:
        from touchless_control.observability import SessionReport

        report = SessionReport(
            total_records=2,
            duration_s=1.0,
            effective_fps=2.0,
            action_count=2,
            dispatch_count=2,
            failure_count=1,
            tracking_loss_count=1,
            p95_latency_ms=40.0,
            p99_latency_ms=40.0,
            primitive_counts={"pointing": 2},
            action_counts={"move_relative": 2},
            move_count=2,
            cursor_update_hz=2.0,
            movement_coverage=1.0,
            move_gap_p50_ms=40.0,
            move_gap_p95_ms=40.0,
            move_gap_max_ms=40.0,
        )

        lines = report.to_lines()

        self.assertIn("session_report total_records=2", lines[0])
        self.assertIn("effective_fps=2.00", lines[0])
        self.assertIn("p95_latency_ms=40.0", lines[0])
        self.assertIn("cursor_update_hz=2.00", lines[0])
        self.assertIn("movement_coverage=1.00", lines[0])
        self.assertIn("move_gap_p95_ms=40.0", lines[0])
        self.assertIn("primitives pointing=2", lines[1])
        self.assertIn("actions move_relative=2", lines[2])


if __name__ == "__main__":
    unittest.main()
