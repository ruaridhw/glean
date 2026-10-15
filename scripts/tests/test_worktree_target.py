import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    ).stdout.strip()


def commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", name)


class TestMakeWorktree(unittest.TestCase):
    """`make worktree` against a throwaway origin and clone.

    Only the dependency installers (uv, flutter) are stubbed; git and make are real.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)

        self.origin = tmp / "origin.git"
        git(tmp, "init", "--bare", "-b", "main", str(self.origin))

        self.seed = tmp / "seed"
        git(tmp, "clone", str(self.origin), str(self.seed))
        git(self.seed, "checkout", "-b", "main")
        for sub in ("backend", "app"):
            (self.seed / sub).mkdir()
            (self.seed / sub / ".keep").write_text("")
        commit(self.seed, "first")
        git(self.seed, "push", "origin", "main")

        self.checkout = tmp / "checkout"
        git(tmp, "clone", str(self.origin), str(self.checkout))
        shutil.copy(REPO_ROOT / "Makefile", self.checkout / "Makefile")

        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for tool in ("uv", "flutter"):
            stub = bin_dir / tool
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}

    def make_worktree(self, **variables: str) -> Path:
        args = [f"{k}={v}" for k, v in variables.items()]
        subprocess.run(
            ["make", "worktree", *args],
            cwd=self.checkout,
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        )
        return self.checkout / ".worktrees" / Path(variables["BRANCH"]).name

    def test_branches_from_current_origin_main_not_the_stale_checkout(self) -> None:
        git(self.checkout, "checkout", "-b", "stale")
        commit(self.checkout, "local-only")
        commit(self.seed, "origin-moved-on")
        git(self.seed, "push", "origin", "main")

        worktree = self.make_worktree(BRANCH="tmp/x")

        origin_main = git(self.origin, "rev-parse", "main")
        self.assertEqual(git(worktree, "rev-parse", "HEAD"), origin_main)
        self.assertEqual(git(worktree, "branch", "--show-current"), "tmp/x")


if __name__ == "__main__":
    unittest.main()
