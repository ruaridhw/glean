"""`scripts/aws_op_profile.sh` against the real AWS CLI and a stand-in for 1Password's `op`.

`aws configure export-credentials` runs the profile's credential_process locally, so these
tests see the key exactly as the CLI would, with no network call.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "aws_op_profile.sh"

# op read REF -> a value derived from the field name; records every reference read.
FAKE_OP = """#!/bin/sh
echo "$2" >> "$STATE/op.reads"
case "$2" in
  */"access key id") printf 'AKIAFAKE' ;;
  */"secret access key") printf 'fake/secret+key' ;;
  *) exit 1 ;;
esac
"""


@unittest.skipUnless(shutil.which("aws"), "needs the AWS CLI")
class TestAwsOpProfile(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        op = bin_dir / "op"
        op.write_text(FAKE_OP)
        op.chmod(op.stat().st_mode | stat.S_IEXEC)
        self.state = tmp / "state"
        self.state.mkdir()
        self.config = tmp / "aws" / "config"
        self.credentials = tmp / "aws" / "credentials"
        env = {k: v for k, v in os.environ.items() if not k.startswith("AWS_")}
        self.env = {
            **env,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STATE": str(self.state),
            "AWS_CONFIG_FILE": str(self.config),
            "AWS_SHARED_CREDENTIALS_FILE": str(self.credentials),
        }

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(SCRIPT), *args], env=self.env, capture_output=True, text=True)

    def export_credentials(self, profile: str) -> dict:
        out = subprocess.run(
            ["aws", "configure", "export-credentials", "--profile", profile, "--format", "process"],
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return json.loads(out)

    def test_profile_reads_the_key_from_1password(self) -> None:
        result = self.run_script("op://My Vault/glean-cli", "glean")
        self.assertEqual(result.returncode, 0, result.stderr)

        creds = self.export_credentials("glean")
        self.assertEqual(creds["AccessKeyId"], "AKIAFAKE")
        self.assertEqual(creds["SecretAccessKey"], "fake/secret+key")
        self.assertEqual(
            (self.state / "op.reads").read_text().splitlines(),
            ["op://My Vault/glean-cli/access key id", "op://My Vault/glean-cli/secret access key"],
        )
        self.assertIn("region = eu-west-2", self.config.read_text())

    def test_helper_lives_beside_the_aws_config_not_in_the_checkout(self) -> None:
        self.run_script("op://v/i")
        helper = self.config.parent / "op-credentials.sh"
        self.assertTrue(os.access(helper, os.X_OK))
        self.assertIn(f'"{helper}" "op://v/i"', self.config.read_text())

    def test_warns_when_static_keys_would_shadow_1password(self) -> None:
        self.credentials.parent.mkdir(parents=True)
        self.credentials.write_text("[glean]\naws_access_key_id = AKIAONDISK\naws_secret_access_key = x\n")

        result = self.run_script("op://v/i", "glean")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("still has aws_access_key_id", result.stderr)

    def test_requires_an_item_reference(self) -> None:
        result = self.run_script("")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OP_AWS_ITEM", result.stderr)


if __name__ == "__main__":
    unittest.main()
