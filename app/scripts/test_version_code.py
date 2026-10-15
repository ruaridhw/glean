"""Behaviour of the shared Android versionCode (docs/adr/0004-timestamp-version-codes.md)."""

import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from version_code import version_code  # noqa: E402

UTC = timezone.utc
SCRIPT = Path(__file__).parent / "version_code.py"


class VersionCodeTest(unittest.TestCase):
    def test_the_epoch_minute_is_zero(self) -> None:
        self.assertEqual(version_code(datetime(2024, 1, 1, 0, 0, tzinfo=UTC)), 0)

    def test_it_counts_whole_minutes(self) -> None:
        self.assertEqual(version_code(datetime(2024, 1, 1, 0, 1, 59, tzinfo=UTC)), 1)

    def test_a_known_instant_matches_a_hand_computed_value(self) -> None:
        # 1018 days (2024 is a leap year) x 1440 + 12 h x 60 = 1_466_640, checked with `date`.
        self.assertEqual(version_code(datetime(2026, 10, 15, 12, 0, tzinfo=UTC)), 1_466_640)

    def test_the_same_instant_in_another_timezone_gives_the_same_code(self) -> None:
        plus_two = timezone(timedelta(hours=2))
        self.assertEqual(version_code(datetime(2026, 10, 15, 14, 0, tzinfo=plus_two)), 1_466_640)

    def test_a_later_build_always_gets_a_higher_code_whichever_pipeline_ran(self) -> None:
        codemagic = version_code(datetime(2026, 10, 15, 12, 0, tzinfo=UTC))
        gordon = version_code(datetime(2026, 10, 15, 12, 1, tzinfo=UTC))
        self.assertGreater(gordon, codemagic)

    def test_the_first_timestamped_build_installs_over_the_current_version_code_4(self) -> None:
        self.assertGreater(version_code(datetime(2026, 10, 15, tzinfo=UTC)), 4)

    def test_it_stays_inside_androids_limit_for_centuries(self) -> None:
        self.assertLess(version_code(datetime(3000, 1, 1, tzinfo=UTC)), 2_100_000_000)

    def test_a_naive_time_is_refused_rather_than_read_as_local_time(self) -> None:
        with self.assertRaises(ValueError):
            version_code(datetime(2026, 10, 15, 12, 0))

    def test_a_time_before_the_epoch_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            version_code(datetime(2023, 12, 31, 23, 59, tzinfo=UTC))


class CommandLineTest(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)

    def test_it_prints_just_the_number_for_a_given_instant(self) -> None:
        result = self.run_script("--at", "2026-10-15T12:00:00+00:00")
        self.assertEqual((result.returncode, result.stdout), (0, "1466640\n"))

    def test_with_no_arguments_it_prints_a_current_code(self) -> None:
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertGreater(int(result.stdout), 1_466_640)  # later than the instant this was written

    def test_a_bad_instant_fails_with_a_message(self) -> None:
        result = self.run_script("--at", "not-a-time")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
