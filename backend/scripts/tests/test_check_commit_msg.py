import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from check_commit_msg import main


def write_commit_message(tmp_path: Path, message: str) -> Path:
    commit_msg = tmp_path / "COMMIT_EDITMSG"
    commit_msg.write_text(message, encoding="utf-8")
    return commit_msg


class TestCommitMessagePolicy:
    def test_accepts_gitmoji_subject_with_body(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        commit_msg = write_commit_message(
            tmp_path,
            "✨ feat: add commit policy\n\nExplain why the commit exists.\n",
        )

        assert main([str(commit_msg)]) == 0
        assert capsys.readouterr().err == ""

    def test_accepts_tooling_gitmoji_subject_with_body(self, tmp_path: Path) -> None:
        commit_msg = write_commit_message(
            tmp_path,
            "🔧 chore: tighten hooks\n\nKeep commit history easier to review.\n",
        )

        assert main([str(commit_msg)]) == 0

    def test_rejects_gitmoji_subject_without_body(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        commit_msg = write_commit_message(tmp_path, "✨ feat: add commit policy\n")

        assert main([str(commit_msg)]) == 1
        assert "You must explain WHY this change exists. Provide context on its reasoning." in capsys.readouterr().err

    def test_rejects_non_gitmoji_subject_with_body(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        commit_msg = write_commit_message(
            tmp_path,
            "feat: add commit policy\n\nExplain why the commit exists.\n",
        )

        assert main([str(commit_msg)]) == 1
        assert "Start the commit subject with a gitmoji/emoji." in capsys.readouterr().err

    @pytest.mark.parametrize(
        "message",
        [
            "",
            "\n\n",
            "# Please enter the commit message for your changes.\n# Lines starting with '#' will be ignored.\n",
        ],
    )
    def test_rejects_empty_or_comment_only_messages(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        message: str,
    ) -> None:
        commit_msg = write_commit_message(tmp_path, message)

        assert main([str(commit_msg)]) == 1
        assert "Commit message subject is required." in capsys.readouterr().err

    def test_ignores_comment_lines_when_finding_body(self, tmp_path: Path) -> None:
        commit_msg = write_commit_message(
            tmp_path,
            "✨ feat: add commit policy\n\n# ignored template hint\nExplain why the commit exists.\n",
        )

        assert main([str(commit_msg)]) == 0

    @pytest.mark.parametrize(
        "message",
        [
            "Merge branch 'main' into feature/demo\n",
            'Revert "✨ feat: add commit policy"\n',
            "fixup! ✨ feat: add commit policy\n",
            "squash! ✨ feat: add commit policy\n",
        ],
    )
    def test_accepts_generated_git_messages(self, tmp_path: Path, message: str) -> None:
        commit_msg = write_commit_message(tmp_path, message)

        assert main([str(commit_msg)]) == 0
