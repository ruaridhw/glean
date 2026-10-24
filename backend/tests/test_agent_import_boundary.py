"""Each library has exactly one owning module, and neither lane is exempt from the other's ban.

`glean.llm` owns LangChain, `glean.agent` owns LangGraph and its checkpointer. The bans are ruff's
`TID251`, enforced per import (`# noqa: TID251` on the owning module's own imports), so
`llm.py` cannot import LangGraph and `agent/` cannot import LangChain. This test pins the
configuration and then asks ruff itself, so a silent config edit fails here too.
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
LLM_MODULE = "src/glean/llm.py"


def _ruff_config() -> dict:
    return tomllib.loads((BACKEND / "pyproject.toml").read_text())


def _banned() -> dict[str, dict[str, str]]:
    return _ruff_config()["tool"]["ruff"]["lint"]["flake8-tidy-imports"]["banned-api"]


def _per_file_ignores() -> dict[str, list[str]]:
    return _ruff_config()["tool"]["ruff"]["lint"]["per-file-ignores"]


@pytest.mark.parametrize(
    ("module", "owner"), [("langgraph", "glean.agent"), ("langgraph_checkpoint_aws", "glean.agent")]
)
def test_langgraph_belongs_to_the_agent_module(module: str, owner: str) -> None:
    assert module in _banned()
    assert owner in _banned()[module]["msg"]


@pytest.mark.parametrize(("module", "owner"), [("langchain_core", "glean.llm"), ("openrouter", "glean.llm")])
def test_langchain_belongs_to_the_llm_module(module: str, owner: str) -> None:
    assert module in _banned()
    assert owner in _banned()[module]["msg"]


def test_no_module_under_src_is_exempt_from_any_ban() -> None:
    """Per-file TID251 exemptions would let one lane import the other's library. Only non-src code is exempt."""
    exempt = [
        pattern for pattern, rules in _per_file_ignores().items() if "TID251" in rules and pattern.startswith("src/")
    ]

    assert exempt == []


def _ruff(import_line: str, filename: str) -> subprocess.CompletedProcess[str]:
    ruff = shutil.which("ruff") or str(BACKEND / ".venv" / "bin" / "ruff")
    return subprocess.run(
        # Concise output names the rule on one line and does not echo the source, so the noqa directive
        # written into the input cannot be mistaken for the rule firing.
        [ruff, "check", "--no-cache", "--output-format", "concise", "--stdin-filename", filename, "-"],
        input=import_line,
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("import_line", "filename"),
    [
        # LangGraph outside the agent module.
        ("import langgraph.graph\n", "src/glean/meal_plan/pipeline.py"),
        ("import langgraph.graph\n", "src/glean/worker.py"),
        ("import langgraph_checkpoint_aws\n", "src/glean/sessions/store.py"),
        # The reverse bypass: LangChain inside the agent module, which used to be exempt wholesale.
        ("from langchain_core.messages import HumanMessage\n", f"{AGENT_MODULE}/graph.py"),
        ("import langchain_openrouter\n", f"{AGENT_MODULE}/runtime.py"),
        # And LangGraph inside the LLM module, the other half of the same hole.
        ("import langgraph.graph\n", LLM_MODULE),
        ("import langgraph_checkpoint_aws\n", LLM_MODULE),
    ],
)
def test_a_cross_lane_import_fails_the_linter(import_line: str, filename: str) -> None:
    result = _ruff(import_line, filename)

    assert result.returncode == 1
    assert "TID251" in result.stdout


@pytest.mark.parametrize(
    ("import_line", "filename"),
    [
        ("import langgraph.graph  # noqa: TID251\n", f"{AGENT_MODULE}/graph.py"),
        ("from langchain_core.messages import HumanMessage  # noqa: TID251\n", LLM_MODULE),
    ],
)
def test_the_owners_own_import_is_exempt_only_where_it_says_so(import_line: str, filename: str) -> None:
    """The escape hatch is the line's `# noqa`, so the owner can import its library and nothing else can."""
    result = _ruff(import_line, filename)

    assert "TID251" not in result.stdout, result.stdout


@pytest.mark.parametrize("filename", [LLM_MODULE, f"{AGENT_MODULE}/checkpoint.py", f"{AGENT_MODULE}/graph.py"])
def test_the_owning_modules_pass_the_linter_as_written(filename: str) -> None:
    """The `# noqa: TID251` markers are on the real imports, so the real files lint clean."""
    ruff = shutil.which("ruff") or str(BACKEND / ".venv" / "bin" / "ruff")
    result = subprocess.run(
        [ruff, "check", "--no-cache", filename], cwd=BACKEND, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stdout


def test_the_checkpointer_is_only_named_inside_the_agent_module() -> None:
    """`langgraph.checkpoint.*` is the agent module's, never the worker's, the routes' or the store's."""
    importers = {
        str(path.relative_to(BACKEND))
        for path in (BACKEND / "src" / "glean").rglob("*.py")
        if "langgraph.checkpoint" in path.read_text()
    }

    assert importers
    assert all(importer.startswith(f"{AGENT_MODULE}/") for importer in importers)
