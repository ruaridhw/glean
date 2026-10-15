"""Deploy the backend to prod, stamped with the commit it was built from.

Used by `make deploy-prod` and by the backend deploy workflow, so both paths deploy identically.
Never blocks a hotfix: a dirty or unpushed tree stops the deploy unless ALLOW_DIRTY=1, in which case
the stamp becomes `<sha>-dirty` and the deploy is logged.
"""

from __future__ import annotations

import getpass
import os
import shlex
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
CONFIG_ENV = "prod"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def _tree_problems() -> list[str]:
    problems = []
    if _git("status", "--porcelain"):
        problems.append("the working tree has uncommitted changes")
    if not _git("branch", "--remotes", "--contains", "HEAD"):
        problems.append("HEAD has not been pushed to the remote")
    return problems


def _config_overrides() -> dict[str, str]:
    """samconfig's prod parameters. Passing --parameter-overrides on the CLI replaces this list wholesale,
    so the deploy re-passes all of it rather than leaving samconfig to be silently dropped."""
    config = tomllib.loads((BACKEND / "samconfig.toml").read_text())
    pairs = shlex.split(config[CONFIG_ENV]["deploy"]["parameters"]["parameter_overrides"])
    return dict(pair.split("=", 1) for pair in pairs)


def _log_deploy(stamp: str, problems: list[str]) -> None:
    log = Path(os.environ.get("GLEAN_DEPLOY_LOG", Path.home() / ".glean" / "deploy.log"))
    log.parent.mkdir(parents=True, exist_ok=True)
    when = datetime.now(UTC).isoformat(timespec="seconds")
    with log.open("a") as handle:
        handle.write(f"{when} {getpass.getuser()} {stamp} {'; '.join(problems)}\n")


def main() -> int:
    problems = _tree_problems()
    if problems and os.environ.get("ALLOW_DIRTY") != "1":
        for problem in problems:
            print(f"Refusing to deploy to prod: {problem}.", file=sys.stderr)
        print("Commit and push first, or set ALLOW_DIRTY=1 to deploy anyway (the stamp will say -dirty).", file=sys.stderr)
        return 1

    sha = _git("rev-parse", "HEAD")
    stamp = f"{sha}-dirty" if problems else sha
    if problems:
        _log_deploy(stamp, problems)

    overrides = {**_config_overrides(), "GitSha": stamp}
    subprocess.run(["sam", "build"], cwd=BACKEND, check=True)
    subprocess.run(
        [
            "sam",
            "deploy",
            "--config-env",
            CONFIG_ENV,
            "--parameter-overrides",
            " ".join(f'{key}="{value}"' for key, value in overrides.items()),
            "--tags",
            f"commit={stamp}",
            "--no-confirm-changeset",
            "--no-fail-on-empty-changeset",
        ],
        cwd=BACKEND,
        check=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
