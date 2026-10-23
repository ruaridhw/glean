"""LangGraph lives behind `glean.agent`, the way LangChain lives behind `glean.llm`.

Both are enforced by ruff's `TID251` rather than by review: a banned import is a lint failure wherever
it appears in `src/glean`, and a per-file exemption grants it to the one module that owns it. This
test pins the configuration and then asks ruff itself, so a silent config edit fails here too.
"""

# ruff: noqa: S603 - runs ruff by name; every argument is built here, none from outside input
from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
AGENT_MODULE = "src/glean/agent"


def _ruff_config() -> dict:
    return tomllib.loads((BACKEND / "pyproject.toml").read_text())


def _banned() -> dict[str, str]:
    return _ruff_config()["tool"]["ruff"]["lint"]["flake8-tidy-imports"]["banned-api"]


def _per_file_ignores() -> dict[str, list[str]]:
    return _ruff_config()["tool"]["ruff"]["lint"]["per-file-ignores"]


@pytest.mark.parametrize("module", ["langgraph", "langgraph_checkpoint_aws"])
def test_langgraph_is_banned_outside_the_agent_module(module: str) -> None:
    assert module in _banned()
    assert "glean.agent" in _banned()[module]["msg"]


def test_only_the_agent_module_is_exempt_from_the_langgraph_ban() -> None:
    exempt = [
        pattern for pattern, rules in _per_file_ignores().items() if "TID251" in rules and pattern.startswith("src/")
    ]

    assert sorted(exempt) == sorted(["src/glean/agent/**", "src/glean/llm.py"])


def _ruff_rejects(import_line: str, filename: str) -> subprocess.CompletedProcess[str]:
    ruff = shutil.which("ruff") or str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "ruff")
    return subprocess.run(
        [ruff, "check", "--no-cache", "--stdin-filename", filename, "-"],
        input=import_line,
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "filename",
    ["src/glean/meal_plan/pipeline.py", "src/glean/worker.py", "src/glean/sessions/store.py"],
)
def test_a_langgraph_import_outside_the_agent_module_fails_the_linter(filename: str) -> None:
    result = _ruff_rejects("import langgraph.graph\n", filename)

    assert result.returncode == 1
    assert "TID251" in result.stdout


def test_the_agent_module_may_import_langgraph() -> None:
    # An unused import is still F401, so the check is that the ban did not fire.
    result = _ruff_rejects("import langgraph.graph\n", f"{AGENT_MODULE}/graph.py")

    assert "TID251" not in result.stdout, result.stdout


def test_the_checkpointer_is_only_named_inside_the_agent_module() -> None:
    """`langgraph.checkpoint.*` is the agent module's, never the worker's, the routes' or the store's."""
    importers = {
        str(path.relative_to(BACKEND))
        for path in (BACKEND / "src" / "glean").rglob("*.py")
        if "langgraph.checkpoint" in path.read_text()
    }

    assert importers
    assert all(importer.startswith(f"{AGENT_MODULE}/") for importer in importers)
