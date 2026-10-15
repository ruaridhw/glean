"""Deploy the backend to prod, stamped with the commit it was built from.

Used by `make deploy-prod` and by the backend deploy workflow, so both paths deploy identically.
Never blocks a hotfix: a dirty or unpushed tree stops the deploy unless ALLOW_DIRTY=1, in which case
the stamp becomes `<sha>-dirty` and the deploy is logged.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def _tree_problems() -> list[str]:
    problems = []
    if _git("status", "--porcelain"):
        problems.append("the working tree has uncommitted changes")
    if not _git("branch", "--remotes", "--contains", "HEAD"):
        problems.append("HEAD has not been pushed to the remote")
    return problems


def main() -> int:
    problems = _tree_problems()
    if problems and os.environ.get("ALLOW_DIRTY") != "1":
        for problem in problems:
            print(f"Refusing to deploy to prod: {problem}.", file=sys.stderr)
        print("Commit and push first, or set ALLOW_DIRTY=1 to deploy anyway (the stamp will say -dirty).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
