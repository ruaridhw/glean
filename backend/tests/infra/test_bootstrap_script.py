"""infra/bootstrap.sh must pass the required AlertEmail parameter to the stack, and never carry the address itself."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.infra.cfn import BOOTSTRAP

if TYPE_CHECKING:
    from pathlib import Path

SCRIPT = BOOTSTRAP.with_suffix(".sh")


@pytest.fixture
def fake_cli(tmp_path: Path) -> Path:
    """`aws` and `sam` stand-ins that log their calls, so the script runs without touching AWS."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.log"
    for name, output in (("aws", "123456789012"), ("sam", "")):
        stub = bin_dir / name
        stub.write_text(f'#!/usr/bin/env bash\necho "{name} $*" >> "{calls}"\necho "{output}"\n')
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return tmp_path


def _run(fake_cli: Path, *args: str, env: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], str]:
    base = {"PATH": f"{fake_cli / 'bin'}:{os.environ['PATH']}", "HOME": str(fake_cli)}
    result = subprocess.run(  # noqa: S603 - runs the repo's own script with stubbed CLIs
        ["bash", str(SCRIPT), *args],  # noqa: S607
        env={**base, **(env or {})},
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    calls = fake_cli / "calls.log"
    return result, calls.read_text() if calls.exists() else ""


def test_without_an_alert_email_it_fails_clearly_before_touching_aws(fake_cli: Path) -> None:
    result, calls = _run(fake_cli)
    assert result.returncode != 0
    assert "ALERT_EMAIL" in result.stderr
    assert calls == ""


def test_the_alert_email_from_the_environment_reaches_the_stack(fake_cli: Path) -> None:
    _, calls = _run(fake_cli, env={"ALERT_EMAIL": "owner@example.test"})
    deploy = next(line for line in calls.splitlines() if line.startswith("sam deploy"))
    assert "AlertEmail=owner@example.test" in deploy


def test_the_alert_email_can_be_given_as_an_argument(fake_cli: Path) -> None:
    _, calls = _run(fake_cli, "owner@example.test")
    assert "AlertEmail=owner@example.test" in calls


def test_the_script_itself_carries_no_email_address() -> None:
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", SCRIPT.read_text(encoding="utf-8"))
