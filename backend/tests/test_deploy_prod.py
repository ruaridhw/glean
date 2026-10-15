# ruff: noqa: S603, S607 - the tests drive git and make by name against a throwaway repo
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
    remote: Path
    stub_dir: Path
    log_file: Path
    env: dict[str, str]

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True, env=self.env
        ).stdout.strip()

    def remote_git(self, *args: str) -> None:
        subprocess.run(["git", "--git-dir", str(self.remote), *args], check=True, capture_output=True, env=self.env)

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
                "LangSmithEndpoint": "https://eu.api.smith.langchain.com",
                "GitSha": stamp,
            },
            lambda_env={
                "ENVIRONMENT": "prod",
                "LANGSMITH_TRACING": "true",
                "LANGSMITH_ENDPOINT": "https://eu.api.smith.langchain.com",
                "GIT_SHA": stamp,
            },
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
    box = Sandbox(root=root, remote=tmp_path / "remote.git", stub_dir=stub_dir, log_file=log_file, env=env)

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


def test_deploy_reports_a_live_mismatch_against_samconfig(sandbox: Sandbox) -> None:
    sha = sandbox.git("rev-parse", "HEAD")
    sandbox.set_live(
        parameters={
            "Environment": "prod",
            "CognitoDomainPrefix": "glean-auth-040396448697",
            "LangSmithTracing": "false",
            "GitSha": sha,
        },
        lambda_env={"ENVIRONMENT": "prod", "LANGSMITH_TRACING": "false", "GIT_SHA": sha},
        tags={"commit": sha},
    )

    result = sandbox.run()

    assert result.returncode != 0
    assert "LangSmithTracing" in result.stderr
    assert "LANGSMITH_TRACING" in result.stderr


def test_deploy_reports_when_the_lambda_does_not_carry_the_stamp(sandbox: Sandbox) -> None:
    sha = sandbox.git("rev-parse", "HEAD")
    sandbox.set_live(
        parameters={
            "Environment": "prod",
            "CognitoDomainPrefix": "glean-auth-040396448697",
            "LangSmithTracing": "true",
            "GitSha": sha,
        },
        lambda_env={"ENVIRONMENT": "prod", "LANGSMITH_TRACING": "true", "GIT_SHA": "unknown"},
        tags={"commit": sha},
    )

    result = sandbox.run()

    assert result.returncode != 0
    assert "GIT_SHA" in result.stderr


def test_deploy_refuses_when_the_pushed_branch_was_deleted_on_origin(sandbox: Sandbox) -> None:
    sandbox.git("checkout", "-q", "-b", "hotfix")
    (sandbox.root / "backend" / "notes.txt").write_text("hotfix")
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", "hotfix")
    sandbox.git("push", "-q", "-u", "origin", "hotfix")
    sandbox.remote_git("branch", "-D", "hotfix")  # deleted remotely; the local origin/hotfix ref is now stale

    result = sandbox.run()

    assert result.returncode != 0
    assert "not been pushed" in result.stderr
    assert sandbox.calls_to("sam") == []


def test_deploy_refuses_when_origin_main_was_rewound_past_head(sandbox: Sandbox) -> None:
    (sandbox.root / "backend" / "notes.txt").write_text("pushed, then rewound")
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", "later")
    sandbox.git("push", "-q", "origin", "main")
    sandbox.remote_git("update-ref", "refs/heads/main", sandbox.git("rev-parse", "HEAD~1"))

    result = sandbox.run()

    assert result.returncode != 0
    assert "not been pushed" in result.stderr
    assert sandbox.calls_to("sam") == []


def test_deploy_accepts_a_head_that_is_only_on_its_pushed_upstream_branch(sandbox: Sandbox) -> None:
    sandbox.git("checkout", "-q", "-b", "hotfix")
    (sandbox.root / "backend" / "notes.txt").write_text("hotfix")
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", "hotfix")
    sandbox.git("push", "-q", "-u", "origin", "hotfix")
    sha = sandbox.git("rev-parse", "HEAD")
    sandbox.set_live_matching_a_deploy_of(sha)

    result = sandbox.run()

    assert result.returncode == 0, result.stderr
    assert sandbox.calls_to("sam", "deploy")


def test_deploy_ignores_pushes_to_other_remotes(sandbox: Sandbox, tmp_path: Path) -> None:
    other = tmp_path / "fork.git"
    subprocess.run(["git", "init", "-q", "--bare", str(other)], check=True)
    sandbox.git("remote", "add", "fork", str(other))
    (sandbox.root / "backend" / "notes.txt").write_text("only on a fork")
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", "fork only")
    sandbox.git("push", "-q", "fork", "main")

    result = sandbox.run()

    assert result.returncode != 0
    assert "not been pushed" in result.stderr


def test_deploy_reports_lambda_env_that_drifted_from_the_stack_parameter_default(sandbox: Sandbox) -> None:
    """LangSmithEndpoint is not in samconfig, so the stack's resolved value is the expectation."""
    sha = sandbox.git("rev-parse", "HEAD")
    sandbox.set_live(
        parameters={
            "Environment": "prod",
            "CognitoDomainPrefix": "glean-auth-040396448697",
            "LangSmithTracing": "true",
            "LangSmithEndpoint": "https://eu.api.smith.langchain.com",
            "GitSha": sha,
        },
        lambda_env={
            "ENVIRONMENT": "prod",
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
            "GIT_SHA": sha,
        },
        tags={"commit": sha},
    )

    result = sandbox.run()

    assert result.returncode != 0
    assert "LANGSMITH_ENDPOINT" in result.stderr


def test_deploy_reports_an_explicit_samconfig_endpoint_that_the_stack_does_not_have(sandbox: Sandbox) -> None:
    config = sandbox.root / "backend" / "samconfig.toml"
    config.write_text(
        config.read_text().replace(
            'LangSmithTracing=\\"true\\"', 'LangSmithTracing=\\"true\\" LangSmithEndpoint=\\"https://example.test\\"', 1
        )
    )
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", "pin endpoint")
    sandbox.git("push", "-q", "origin", "main")
    sandbox.set_live_matching_a_deploy_of(sandbox.git("rev-parse", "HEAD"))  # live still has the default endpoint

    result = sandbox.run()

    assert result.returncode != 0
    assert "LangSmithEndpoint" in result.stderr
    assert "LANGSMITH_ENDPOINT" in result.stderr


def test_deploy_reports_a_missing_lambda_env_var(sandbox: Sandbox) -> None:
    sha = sandbox.git("rev-parse", "HEAD")
    sandbox.set_live_matching_a_deploy_of(sha)
    canned = json.loads((sandbox.stub_dir / "canned.json").read_text())
    del canned["lambda get-function-configuration"]["Environment"]["Variables"]["LANGSMITH_ENDPOINT"]
    (sandbox.stub_dir / "canned.json").write_text(json.dumps(canned))

    result = sandbox.run()

    assert result.returncode != 0
    assert "LANGSMITH_ENDPOINT" in result.stderr
