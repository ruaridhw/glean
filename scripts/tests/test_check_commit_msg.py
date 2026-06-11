import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_commit_msg import main


def write_commit_message(tmp_path: Path, message: str) -> Path:
    commit_msg = tmp_path / "COMMIT_EDITMSG"
    commit_msg.write_text(message, encoding="utf-8")
    return commit_msg


def run_main(commit_msg: Path) -> tuple[int, str]:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        exit_code = main([str(commit_msg)])
    return exit_code, stderr.getvalue()


class TestCommitMessagePolicy(unittest.TestCase):
    def test_accepts_gitmoji_subject_with_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            commit_msg = write_commit_message(
                Path(tmp_dir),
                "✨ feat: add commit policy\n\nExplain why the commit exists.\n",
            )

            self.assertEqual(main([str(commit_msg)]), 0)

    def test_accepts_tooling_gitmoji_subject_with_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            commit_msg = write_commit_message(
                Path(tmp_dir),
                "🔧 chore: tighten hooks\n\nKeep commit history easier to review.\n",
            )

            self.assertEqual(main([str(commit_msg)]), 0)

    def test_rejects_gitmoji_subject_without_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            commit_msg = write_commit_message(Path(tmp_dir), "✨ feat: add commit policy\n")

            exit_code, stderr = run_main(commit_msg)

            self.assertEqual(exit_code, 1)
            self.assertEqual(
                stderr,
                "commit-msg-policy: You must explain WHY this change exists. Provide context on its reasoning.\n",
            )

    def test_rejects_non_gitmoji_subject_with_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            commit_msg = write_commit_message(
                Path(tmp_dir),
                "feat: add commit policy\n\nExplain why the commit exists.\n",
            )

            exit_code, stderr = run_main(commit_msg)

            self.assertEqual(exit_code, 1)
            self.assertEqual(stderr, "commit-msg-policy: Start the commit subject with a gitmoji/emoji.\n")

    def test_rejects_empty_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            commit_msg = write_commit_message(Path(tmp_dir), "")

            exit_code, stderr = run_main(commit_msg)

            self.assertEqual(exit_code, 1)
            self.assertEqual(stderr, "commit-msg-policy: Commit message subject is required.\n")

    def test_rejects_comment_only_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            commit_msg = write_commit_message(
                Path(tmp_dir),
                "# Please enter the commit message for your changes.\n# Lines starting with '#' will be ignored.\n",
            )

            exit_code, stderr = run_main(commit_msg)

            self.assertEqual(exit_code, 1)
            self.assertEqual(stderr, "commit-msg-policy: Commit message subject is required.\n")

    def test_ignores_comment_lines_when_finding_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            commit_msg = write_commit_message(
                Path(tmp_dir),
                "✨ feat: add commit policy\n\n# ignored template hint\nExplain why the commit exists.\n",
            )

            self.assertEqual(main([str(commit_msg)]), 0)

    def test_accepts_generated_git_messages(self) -> None:
        messages = [
            "Merge branch 'main' into feature/demo\n",
            'Revert "✨ feat: add commit policy"\n',
            "fixup! ✨ feat: add commit policy\n",
            "squash! ✨ feat: add commit policy\n",
        ]

        for message in messages:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as tmp_dir:
                commit_msg = write_commit_message(Path(tmp_dir), message)

                self.assertEqual(main([str(commit_msg)]), 0)


if __name__ == "__main__":
    unittest.main()
