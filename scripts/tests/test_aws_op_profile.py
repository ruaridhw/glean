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

# op inject: fills {{ REF }} with a value derived from the field name; records the template.
FAKE_OP = """#!/bin/sh
[ "$1" = inject ] || exit 1
tee -a "$STATE/op.templates" \\
  | sed -e 's#{{ [^}]*/access key id }}#AKIAFAKE#' -e 's#{{ [^}]*/secret access key }}#fake/secret+key#'
"""

# ssh [-o OPT]... HOST CMD: records the host (and, separately, the hosts `op inject` ran on), fails
# like an unreachable machine for hosts listed in $UNREACHABLE, else runs CMD here as the remote
# shell would.
FAKE_SSH = """#!/bin/sh
while [ "$1" = -o ]; do shift 2; done
echo "$1" >> "$STATE/ssh.hosts"
case " $UNREACHABLE " in *" $1 "*) exit 255 ;; esac
case "$2" in *"op inject"*) echo "$1" >> "$STATE/ssh.op_hosts" ;; esac
exec sh -c "$2"
"""


@unittest.skipUnless(shutil.which("aws"), "needs the AWS CLI")
class TestAwsOpProfile(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name, body in (("op", FAKE_OP), ("ssh", FAKE_SSH)):
            tool = bin_dir / name
            tool.write_text(body)
            tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
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
        template = (self.state / "op.templates").read_text()
        self.assertIn("{{ op://My Vault/glean-cli/access key id }}", template)
        self.assertIn("{{ op://My Vault/glean-cli/secret access key }}", template)
        self.assertFalse((self.state / "ssh.hosts").exists())
        self.assertIn("region = eu-west-2", self.config.read_text())

    def test_ssh_host_runs_op_on_that_machine(self) -> None:
        result = self.run_script("op://v/i", "glean", "me@mac")
        self.assertEqual(result.returncode, 0, result.stderr)

        creds = self.export_credentials("glean")

        self.assertEqual(creds["AccessKeyId"], "AKIAFAKE")
        self.assertEqual(creds["SecretAccessKey"], "fake/secret+key")
        self.assertEqual((self.state / "ssh.hosts").read_text().splitlines(), ["me@mac"])


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


SESSION_SCRIPT = Path(__file__).resolve().parents[1] / "aws_op_session.sh"

# aws: only the two calls the session script makes. STS_FAIL makes the mint fail like a locked 1Password.
FAKE_AWS = """#!/bin/sh
case "$1 $2" in
  "sts get-session-token")
    [ -z "$STS_FAIL" ] || { echo "Touch ID timed out" >&2; exit 254; }
    echo '{"Credentials":{"AccessKeyId":"ASIAFAKE","SecretAccessKey":"fake/session+secret","SessionToken":"fake-token","Expiration":"2030-01-01T00:00:00+00:00"}}'
    ;;
  "configure get") echo eu-west-2 ;;
  *) exit 1 ;;
esac
"""


class TestAwsOpSession(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        aws = bin_dir / "aws"
        aws.write_text(FAKE_AWS)
        aws.chmod(aws.stat().st_mode | stat.S_IEXEC)
        self.runtime = tmp / "run"
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "XDG_RUNTIME_DIR": str(self.runtime),
        }
        self.cache = self.runtime / "aws-glean-session.env"

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(SESSION_SCRIPT), *args], env=self.env, capture_output=True, text=True)

    def test_caches_a_sourceable_session_owner_only(self) -> None:
        result = self.run_script("glean")
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertEqual(stat.S_IMODE(self.cache.stat().st_mode), 0o600)
        sourced = subprocess.run(
            ["sh", "-c", f". {self.cache} && echo $AWS_ACCESS_KEY_ID $AWS_SECRET_ACCESS_KEY $AWS_SESSION_TOKEN $AWS_DEFAULT_REGION"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        self.assertEqual(sourced, ["ASIAFAKE", "fake/session+secret", "fake-token", "eu-west-2"])
        self.assertIn("# expires 2030-01-01T00:00:00+00:00", self.cache.read_text())

    def test_the_secret_never_appears_in_what_it_prints(self) -> None:
        result = self.run_script("glean")
        self.assertNotIn("fake/session+secret", result.stdout + result.stderr)
        self.assertNotIn("fake-token", result.stdout + result.stderr)

    def test_a_failed_mint_keeps_the_previous_session(self) -> None:
        self.runtime.mkdir()
        self.cache.write_text("# expires earlier\nexport OLD=1\n")
        self.env["STS_FAIL"] = "1"

        result = self.run_script("glean")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.cache.read_text(), "# expires earlier\nexport OLD=1\n")
        self.assertEqual([p.name for p in self.runtime.iterdir()], ["aws-glean-session.env"])


if __name__ == "__main__":
    unittest.main()
