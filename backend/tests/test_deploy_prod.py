"""`make deploy-prod`, run end to end against a throwaway git repo.

Only the system boundaries are faked: `sam` and `aws` are stubs on PATH that record their calls.
git, make and the deploy script itself are real.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

_STUB = """\
#!{python}
import json, os, sys
from pathlib import Path

stub_dir = Path(os.environ["STUB_DIR"])
with (stub_dir / "calls.log").open("a") as log:
    log.write(json.dumps([Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")
canned = json.loads((stub_dir / "canned.json").read_text())
answer = canned.get(" ".join(sys.argv[1:3]))
if answer is not None:
    print(json.dumps(answer))
"""


@dataclass
class Sandbox:
    root: Path
    stub_dir: Path
    log_file: Path
    env: dict[str, str]

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True, env=self.env
        ).stdout.strip()

    def run(self, **extra_env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "deploy-prod"], cwd=self.root, capture_output=True, text=True, env={**self.env, **extra_env}
        )

    def calls(self) -> list[list[str]]:
        log = self.stub_dir / "calls.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def calls_to(self, tool: str, subcommand: str | None = None) -> list[list[str]]:
        return [c for c in self.calls() if c[0] == tool and (subcommand is None or c[1] == subcommand)]

    def set_live(self, *, parameters: dict[str, str], lambda_env: dict[str, str], tags: dict[str, str]) -> None:
        canned = {
            "cloudformation describe-stacks": {
                "Stacks": [
                    {
                        "Parameters": [{"ParameterKey": k, "ParameterValue": v} for k, v in parameters.items()],
                        "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
                    }
                ]
            },
            "cloudformation describe-stack-resource": {"StackResourceDetail": {"PhysicalResourceId": "glean-fn"}},
            "lambda get-function-configuration": {"Environment": {"Variables": lambda_env}},
        }
        (self.stub_dir / "canned.json").write_text(json.dumps(canned))

    def set_live_matching_a_deploy_of(self, stamp: str) -> None:
        self.set_live(
            parameters={
                "Environment": "prod",
                "CognitoDomainPrefix": "glean-auth-040396448697",
                "LangSmithTracing": "true",
                "GitSha": stamp,
            },
            lambda_env={"ENVIRONMENT": "prod", "LANGSMITH_TRACING": "true", "GIT_SHA": stamp},
            tags={"commit": stamp},
        )


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    root = tmp_path / "work"
    (root / "backend" / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "Makefile", root / "Makefile")
    shutil.copy(REPO / "backend" / "samconfig.toml", root / "backend" / "samconfig.toml")
    shutil.copy(REPO / "backend" / "scripts" / "deploy_prod.py", root / "backend" / "scripts" / "deploy_prod.py")

    stub_dir = tmp_path / "stubs"
    bin_dir = tmp_path / "bin"
    stub_dir.mkdir()
    bin_dir.mkdir()
    for tool in ("sam", "aws"):
        stub = bin_dir / tool
        stub.write_text(_STUB.format(python=sys.executable))
        stub.chmod(0o755)
    (stub_dir / "canned.json").write_text("{}")

    log_file = tmp_path / "deploys.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_DIR": str(stub_dir),
        "GLEAN_DEPLOY_LOG": str(log_file),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    env.pop("ALLOW_DIRTY", None)
    box = Sandbox(root=root, stub_dir=stub_dir, log_file=log_file, env=env)

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    box.git("init", "-q", "-b", "main")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "initial")
    box.git("remote", "add", "origin", str(remote))
    box.git("push", "-q", "-u", "origin", "main")
    return box


def test_deploy_stops_on_a_dirty_tree_and_says_why(sandbox: Sandbox) -> None:
    (sandbox.root / "backend" / "notes.txt").write_text("uncommitted")

    result = sandbox.run()

    assert result.returncode != 0
    assert "uncommitted changes" in result.stderr
    assert "ALLOW_DIRTY=1" in result.stderr
    assert sandbox.calls_to("sam") == []


def test_deploy_stops_when_head_is_not_pushed_and_says_why(sandbox: Sandbox) -> None:
    (sandbox.root / "backend" / "notes.txt").write_text("committed locally")
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", "local only")

    result = sandbox.run()

    assert result.returncode != 0
    assert "not been pushed" in result.stderr
    assert sandbox.calls_to("sam") == []


def test_clean_pushed_deploy_stamps_the_commit_on_the_stack_and_lambda(sandbox: Sandbox) -> None:
    sha = sandbox.git("rev-parse", "HEAD")
    sandbox.set_live_matching_a_deploy_of(sha)

    result = sandbox.run()

    assert result.returncode == 0, result.stderr
    (deploy,) = sandbox.calls_to("sam", "deploy")
    assert deploy[deploy.index("--tags") + 1] == f"commit={sha}"
    overrides = deploy[deploy.index("--parameter-overrides") + 1]
    assert f'GitSha="{sha}"' in overrides
    assert deploy[deploy.index("--config-env") + 1] == "prod"


def test_deploy_passes_every_prod_parameter_from_samconfig_and_no_google_values(sandbox: Sandbox) -> None:
    sandbox.set_live_matching_a_deploy_of(sandbox.git("rev-parse", "HEAD"))

    sandbox.run()

    (deploy,) = sandbox.calls_to("sam", "deploy")
    overrides = deploy[deploy.index("--parameter-overrides") + 1]
    assert 'Environment="prod"' in overrides
    assert 'CognitoDomainPrefix="glean-auth-040396448697"' in overrides
    assert 'LangSmithTracing="true"' in overrides
    assert "Google" not in overrides


def test_allow_dirty_deploys_a_dirty_tree_stamped_dirty_and_logs_it(sandbox: Sandbox) -> None:
    sha = sandbox.git("rev-parse", "HEAD")
    (sandbox.root / "backend" / "notes.txt").write_text("hotfix in progress")
    sandbox.set_live_matching_a_deploy_of(f"{sha}-dirty")

    result = sandbox.run(ALLOW_DIRTY="1")

    assert result.returncode == 0, result.stderr
    (deploy,) = sandbox.calls_to("sam", "deploy")
    assert deploy[deploy.index("--tags") + 1] == f"commit={sha}-dirty"
    assert f'GitSha="{sha}-dirty"' in deploy[deploy.index("--parameter-overrides") + 1]
    assert f"{sha}-dirty" in sandbox.log_file.read_text()


def test_allow_dirty_deploys_an_unpushed_commit_stamped_dirty(sandbox: Sandbox) -> None:
    (sandbox.root / "backend" / "notes.txt").write_text("committed locally")
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", "local only")
    sha = sandbox.git("rev-parse", "HEAD")
    sandbox.set_live_matching_a_deploy_of(f"{sha}-dirty")

    result = sandbox.run(ALLOW_DIRTY="1")

    assert result.returncode == 0, result.stderr
    (deploy,) = sandbox.calls_to("sam", "deploy")
    assert deploy[deploy.index("--tags") + 1] == f"commit={sha}-dirty"


def test_clean_deploy_is_not_logged_as_dirty(sandbox: Sandbox) -> None:
    sandbox.set_live_matching_a_deploy_of(sandbox.git("rev-parse", "HEAD"))

    sandbox.run()

    assert not sandbox.log_file.exists() or "dirty" not in sandbox.log_file.read_text()

