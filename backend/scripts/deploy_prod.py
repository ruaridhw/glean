# ruff: noqa: S603, S607 - runs git, sam and aws by name; every argument is built here, none from user input
"""Deploy the backend to prod, stamped with the commit it was built from.

Used by `make deploy-prod` and by the backend deploy workflow, so both paths deploy identically.
Never blocks a hotfix: a dirty or unpushed tree stops the deploy unless ALLOW_DIRTY=1, in which case
the stamp becomes `<sha>-dirty` and the deploy is logged.
"""

from __future__ import annotations

import getpass
import json
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
# Template parameter -> Lambda environment variable it feeds (see template.yaml).
PARAMETER_ENV_VARS = {
    "Environment": "ENVIRONMENT",
    "LangSmithTracing": "LANGSMITH_TRACING",
    "LangSmithEndpoint": "LANGSMITH_ENDPOINT",
    "GitSha": "GIT_SHA",
    "RateLimitPerHour": "RATE_LIMIT_PER_HOUR",
    "RecipeStore": "RECIPE_STORE",
}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def _git_ok(*args: str) -> bool:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True).returncode == 0


def _head_is_on_origin() -> bool:
    """True when HEAD is contained in a freshly fetched origin/main or in this branch's upstream on origin.

    Cached remote-tracking refs and other remotes are not trusted: a branch deleted or rewound on origin
    would otherwise still look pushed."""
    if not _git_ok("fetch", "--quiet", "--prune", "origin"):
        return False
    refs = ["origin/main"]
    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if upstream.startswith("origin/"):
        refs.append(upstream)
    return any(
        _git_ok("rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}")
        and _git_ok("merge-base", "--is-ancestor", "HEAD", f"refs/remotes/{ref}")
        for ref in refs
    )


def _tree_problems() -> list[str]:
    problems = []
    if _git("status", "--porcelain"):
        problems.append("the working tree has uncommitted changes")
    if not _head_is_on_origin():
        problems.append("HEAD has not been pushed to origin (origin/main or this branch's upstream, freshly fetched)")
    return problems


def _deploy_config() -> dict[str, str]:
    return tomllib.loads((BACKEND / "samconfig.toml").read_text())[CONFIG_ENV]["deploy"]["parameters"]


def _config_overrides() -> dict[str, str]:
    """samconfig's prod parameters. Passing --parameter-overrides on the CLI replaces this list wholesale,
    so the deploy re-passes all of it rather than leaving samconfig to be silently dropped."""
    pairs = shlex.split(_deploy_config()["parameter_overrides"])
    return dict(pair.split("=", 1) for pair in pairs)


def _aws(*args: str) -> dict:
    out = subprocess.run(["aws", *args, "--output", "json"], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def _live_mismatches(overrides: dict[str, str], stamp: str) -> list[str]:
    """Compare the deployed stack and Lambda with what this deploy asked for."""
    stack_name, region = _deploy_config()["stack_name"], _deploy_config()["region"]
    stack = _aws("cloudformation", "describe-stacks", "--stack-name", stack_name, "--region", region)["Stacks"][0]
    function = _aws(
        "cloudformation",
        "describe-stack-resource",
        "--stack-name",
        stack_name,
        "--logical-resource-id",
        "GleanFunction",
        "--region",
        region,
    )["StackResourceDetail"]["PhysicalResourceId"]
    lambda_env = _aws("lambda", "get-function-configuration", "--function-name", function, "--region", region)[
        "Environment"
    ]["Variables"]

    live_params = {p["ParameterKey"]: p["ParameterValue"] for p in stack.get("Parameters", [])}
    live_tags = {t["Key"]: t["Value"] for t in stack.get("Tags", [])}
    # Parameters samconfig leaves out resolve to template defaults, so the stack's resolved value is the
    # expectation for the Lambda env; samconfig's own values are checked against the stack above.
    expected_params = {**live_params, **overrides}
    checks = [
        *((f"stack parameter {key}", live_params.get(key), value) for key, value in overrides.items()),
        ("stack tag commit", live_tags.get("commit"), stamp),
        *(
            (f"Lambda env {env_var}", lambda_env.get(env_var), expected_params.get(param))
            for param, env_var in PARAMETER_ENV_VARS.items()
            if param in expected_params
        ),
    ]
    return [f"{what}: live {live!r}, expected {want!r}" for what, live, want in checks if live != want]


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
        print(
            "Commit and push first, or set ALLOW_DIRTY=1 to deploy anyway (the stamp will say -dirty).", file=sys.stderr
        )
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

    mismatches = _live_mismatches(overrides, stamp)
    for mismatch in mismatches:
        print(f"Post-deploy mismatch: {mismatch}", file=sys.stderr)
    return 2 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
