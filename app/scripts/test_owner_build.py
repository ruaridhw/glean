"""Behaviour of the gordon owner-build script, run against stand-ins for the tools it drives (1Password's `op`,
`flutter`, the SDK's `apksigner` and `aapt2`, and `adb`, which it must never call)."""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "owner_build.sh"
CERT = "AB:CD:EF:01"

FAKE_OP = """#!/bin/sh
# op read [--out-file F --force] REF
out=""
while [ $# -gt 0 ]; do case "$1" in --out-file) out="$2"; shift;; esac; shift; done
if [ -n "$out" ]; then printf 'JKS-BYTES' > "$out"; else printf 'secret-value'; fi
"""

FAKE_FLUTTER = """#!/bin/sh
echo "$@" > "$STATE/flutter.args"
echo "GLEAN_OWNER_BUILD=${GLEAN_OWNER_BUILD:-}" > "$STATE/flutter.env"
echo "KEYSTORE_PATH=$CM_KEYSTORE_PATH" >> "$STATE/flutter.env"
stat -c '%a' "$CM_KEYSTORE_PATH" > "$STATE/keystore.mode"
cat "$CM_KEYSTORE_PATH" > "$STATE/keystore.seen"
[ "${FAKE_FLUTTER_FAILS:-}" = "1" ] && exit 1
[ "${FAKE_FLUTTER_NO_OUTPUT:-}" = "1" ] && exit 0
mkdir -p build/app/outputs/flutter-apk
: > build/app/outputs/flutter-apk/app-release.apk
"""

# The real apksigner prints certificate digests only with --verbose --print-certs.
FAKE_APKSIGNER = """#!/bin/sh
case " $* " in *" --verbose "*) ;; *) echo Verified; exit 0;; esac
echo "Signer #1 certificate SHA-256 digest: $FAKE_SIGNER_CERT"
"""

FAKE_AAPT2 = """#!/bin/sh
code=$(sed -n 's/.*--build-number=\\([0-9]*\\).*/\\1/p' "$STATE/flutter.args")
echo "package: name='com.ruaridhw.glean' versionCode='$code' versionName='1.0.0'"
echo "application-debuggable"
"""

FAKE_ADB = """#!/bin/sh
echo "$@" >> "$STATE/adb.calls"
"""


class OwnerBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.state = root / "state"
        self.state.mkdir()
        self.bin = root / "bin"
        self.bin.mkdir()
        sdk = root / "sdk" / "build-tools" / "36.0.0"
        sdk.mkdir(parents=True)
        for directory, name, body in (
            (self.bin, "op", FAKE_OP),
            (self.bin, "flutter", FAKE_FLUTTER),
            (self.bin, "adb", FAKE_ADB),
            (sdk, "apksigner", FAKE_APKSIGNER),
            (sdk, "aapt2", FAKE_AAPT2),
        ):
            path = directory / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        app = root / "app"
        (app).mkdir()
        (app / "pubspec.yaml").write_text("version: 1.0.0+1\n")
        self.env = {
            "GLEAN_APP_DIR": str(app),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "HOME": str(root),
            "STATE": str(self.state),
            "ANDROID_SDK_ROOT": str(root / "sdk"),
            "TMPDIR": str(root),
            "API_BASE_URL": "https://api.example.test",
            "COGNITO_DOMAIN": "auth.example.test",
            "COGNITO_CLIENT_ID": "client-id",
            "EXPECTED_SIGNING_CERT_SHA256": CERT,
            "OP_KEYSTORE_REF": "op://vault/glean-release/keystore.jks",
            "OP_KEYSTORE_PASSWORD_REF": "op://vault/glean-release/store-password",
            "OP_KEY_PASSWORD_REF": "op://vault/glean-release/key-password",
            "FAKE_SIGNER_CERT": CERT.replace(":", "").lower(),
        }

    def run_script(self, **overrides: str | None) -> subprocess.CompletedProcess[str]:
        env = {**self.env}
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False, env=env)

    def read(self, name: str) -> str:
        return (self.state / name).read_text()

    def test_it_builds_a_debuggable_owner_build_with_a_timestamp_version_code(self) -> None:
        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GLEAN_OWNER_BUILD=1", self.read("flutter.env"))
        code = int(self.read("flutter.args").split("--build-number=")[1].split()[0])
        self.assertGreater(code, 1_466_640)
        self.assertIn("-t lib/main.dart", self.read("flutter.args"))

    def test_the_signing_key_is_private_while_building_and_gone_afterwards(self) -> None:
        self.run_script()

        self.assertEqual(self.read("keystore.mode").strip(), "600")
        self.assertEqual(self.read("keystore.seen"), "JKS-BYTES")
        keystore = self.read("flutter.env").split("KEYSTORE_PATH=")[1].strip()
        self.assertFalse(Path(keystore).exists())

    def test_the_signing_key_is_removed_even_when_the_build_fails(self) -> None:
        result = self.run_script(FAKE_FLUTTER_FAILS="1")

        self.assertNotEqual(result.returncode, 0)
        keystore = self.read("flutter.env").split("KEYSTORE_PATH=")[1].strip()
        self.assertFalse(Path(keystore).exists())

    def test_passwords_never_appear_on_a_command_line_or_in_output(self) -> None:
        result = self.run_script()

        self.assertNotIn("secret-value", self.read("flutter.args"))
        self.assertNotIn("secret-value", result.stdout + result.stderr)

    def test_a_build_signed_with_the_wrong_key_is_rejected(self) -> None:
        result = self.run_script(FAKE_SIGNER_CERT="deadbeef")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fingerprint", result.stderr)

    def test_an_apk_left_by_an_earlier_build_is_never_mistaken_for_this_one(self) -> None:
        stale = Path(self.env["GLEAN_APP_DIR"]) / "build/app/outputs/flutter-apk/app-release.apk"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"tester build")

        result = self.run_script(FAKE_FLUTTER_NO_OUTPUT="1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not produce", result.stderr)

    def test_it_never_installs_anything(self) -> None:
        result = self.run_script()

        self.assertFalse((self.state / "adb.calls").exists())
        self.assertIn("adb", result.stdout)  # prints the install command for a person to run
        self.assertIn("install -r", result.stdout)

    def test_missing_configuration_fails_before_the_password_manager_is_touched(self) -> None:
        result = self.run_script(OP_KEYSTORE_REF=None)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OP_KEYSTORE_REF", result.stderr)
        self.assertFalse((self.state / "flutter.args").exists())


if __name__ == "__main__":
    unittest.main()
