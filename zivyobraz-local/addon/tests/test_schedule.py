import unittest
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schedule import sleep_seconds, validate


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.options = {"sleep_seconds": 360, "timezone": "Europe/Prague", "update_mode": "daily",
                        "update_times": ["07:00", "12:00", "18:00"],
                        "window_start": "07:00", "window_end": "22:00", "window_interval_minutes": 30}

    def sleep(self, iso):
        return sleep_seconds(self.options, datetime.fromisoformat(iso))

    def test_daily_and_next_morning(self):
        self.assertEqual(self.sleep("2026-10-11T05:00:20+00:00"), 17980)
        self.assertEqual(self.sleep("2026-10-11T16:01:00+00:00"), 46740)

    def test_interval_backward_compatibility(self):
        self.options["update_mode"] = "interval"
        self.assertEqual(self.sleep("2026-10-11T00:00:00+00:00"), 360)

    def test_window_day_night_and_end_exclusive(self):
        self.options["update_mode"] = "window"
        self.assertEqual(self.sleep("2026-10-11T05:10:00+00:00"), 1200)
        self.assertEqual(self.sleep("2026-10-11T19:30:00+00:00"), 34200)

    def test_window_crossing_midnight(self):
        self.options.update(update_mode="window", window_start="22:00", window_end="07:00")
        self.assertEqual(self.sleep("2026-10-11T21:45:00+00:00"), 900)
        self.assertEqual(self.sleep("2026-10-11T05:00:00+00:00"), 54000)

    def test_dst_spring_missing_time(self):
        self.options["update_times"] = ["02:30", "07:00"]
        self.assertEqual(self.sleep("2026-03-29T00:45:00+00:00"), 15300)

    def test_dst_autumn_both_folds(self):
        self.options["update_times"] = ["02:30"]
        self.assertEqual(self.sleep("2026-10-25T00:31:00+00:00"), 3540)

    def test_minimum_sleep_does_not_skip_near_slot(self):
        self.assertEqual(self.sleep("2026-10-11T04:59:30+00:00"), 60)

    def test_validation(self):
        validate(self.options)
        for change in ({"update_times": []}, {"update_times": ["7:00"]}, {"update_times": ["24:00"]},
                       {"window_start": "22:00"}, {"timezone": "Missing/Zone"},
                       {"window_interval_minutes": True}, {"update_mode": "invalid"}):
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                validate(self.options | change)


if __name__ == "__main__":
    unittest.main()
