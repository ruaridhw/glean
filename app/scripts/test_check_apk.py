"""Behaviour of the APK gate: tester builds must not be debuggable, the owner build must be, and the
versionCode must be the one the build was asked for."""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_apk import parse_badging, problems  # noqa: E402

SCRIPT = Path(__file__).parent / "check_apk.py"

# Shaped like `aapt2 dump badging` output; the debuggable one differs by the standalone flag line.
RELEASE_BADGING = """\
package: name='com.ruaridhw.glean' versionCode='1466640' versionName='1.0.0' platformBuildVersionCode='36' compileSdkVersion='36'
sdkVersion:'24'
targetSdkVersion:'36'
uses-permission: name='android.permission.CAMERA'
application-label:'Glean'
application: label='Glean' icon='res/mipmap-mdpi-v4/ic_launcher.png'
launchable-activity: name='com.ruaridhw.glean.MainActivity'  label='' icon=''
"""
OWNER_BADGING = RELEASE_BADGING.replace("application-label:", "application-debuggable\napplication-label:")


class ParseBadgingTest(unittest.TestCase):
    def test_reads_package_and_version_code(self) -> None:
        facts = parse_badging(RELEASE_BADGING)
        self.assertEqual((facts.package, facts.version_code), ("com.ruaridhw.glean", 1466640))

    def test_a_release_apk_is_not_debuggable(self) -> None:
        self.assertFalse(parse_badging(RELEASE_BADGING).debuggable)

    def test_the_debuggable_flag_line_marks_a_debuggable_apk(self) -> None:
        self.assertTrue(parse_badging(OWNER_BADGING).debuggable)

    def test_a_permission_or_label_mentioning_debuggable_is_not_the_flag(self) -> None:
        tricky = RELEASE_BADGING + "application-label-fr:'application-debuggable'\n"
        self.assertFalse(parse_badging(tricky).debuggable)

    def test_output_with_no_package_line_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_badging("sdkVersion:'24'\n")


class ProblemsTest(unittest.TestCase):
    def test_a_non_debuggable_tester_build_with_the_right_code_passes(self) -> None:
        facts = parse_badging(RELEASE_BADGING)
        self.assertEqual(problems(facts, expect="release", version_code=1466640), [])

    def test_a_debuggable_apk_fails_the_tester_gate(self) -> None:
        facts = parse_badging(OWNER_BADGING)
        self.assertTrue(any("debuggable" in p for p in problems(facts, expect="release")))

    def test_a_non_debuggable_apk_fails_the_owner_gate(self) -> None:
        facts = parse_badging(RELEASE_BADGING)
        self.assertTrue(any("not debuggable" in p for p in problems(facts, expect="owner")))

    def test_a_wrong_version_code_fails(self) -> None:
        facts = parse_badging(RELEASE_BADGING)
        self.assertTrue(any("versionCode" in p for p in problems(facts, expect="release", version_code=5)))

    def test_a_different_application_id_fails(self) -> None:
        facts = parse_badging(RELEASE_BADGING.replace("com.ruaridhw.glean'", "com.example.other'", 1))
        self.assertTrue(any("application id" in p for p in problems(facts, expect="release")))


class CommandLineTest(unittest.TestCase):
    def run_gate(self, badging: str, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "aapt2"
            fake.write_text(f"#!/bin/sh\ncat <<'EOF'\n{badging}EOF\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            apk = Path(tmp) / "app.apk"
            apk.write_bytes(b"")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(apk), "--aapt2", str(fake), *args],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ},
            )

    def test_passes_with_exit_zero(self) -> None:
        result = self.run_gate(RELEASE_BADGING, "--expect", "release", "--version-code", "1466640")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_debuggable_tester_apk_exits_nonzero_and_says_why(self) -> None:
        result = self.run_gate(OWNER_BADGING, "--expect", "release")
        self.assertEqual(result.returncode, 1)
        self.assertIn("debuggable", result.stderr)


if __name__ == "__main__":
    unittest.main()
