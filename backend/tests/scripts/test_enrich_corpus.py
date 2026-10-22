"""The enrichment CLI: dev/local by default, prod only for the owner, and full coverage as the gate."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from scripts import enrich_corpus
from tests.recipes.enrichment.fakes import FakeDecisionApi

from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.search_index import INDEX_KEY
from glean.recipes.stored import StoredIngredient, StoredRecipe


def test_a_dry_run_prints_what_would_be_asked_and_needs_no_api_key(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    corpus = _corpus(tmp_path)

    code = enrich_corpus.main(["--local", str(tmp_path), "--dry-run"])

    out = capsys.readouterr().out
    assert code == 0
    assert "Dry run: 2 recipes would be asked; nothing was requested or stored." in out
    assert "Coverage: 0/12 (0.0%)" in out
    assert corpus.answers() == []


def test_a_complete_run_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _corpus(tmp_path)

    code = enrich_corpus.main(["--local", str(tmp_path)], client=FakeDecisionApi().client())

    assert code == 0
    assert "Coverage: 12/12 (100.0%)" in capsys.readouterr().out


def test_an_incomplete_run_exits_nonzero_so_the_gate_can_fail(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _corpus(tmp_path)
    failing = FakeDecisionApi(fail_when=lambda body: body["state"]["recipe_title"] == "Tomato Pasta")

    code = enrich_corpus.main(["--local", str(tmp_path)], client=failing.client())

    out = capsys.readouterr().out
    assert code == 1
    assert "rec_tomato" in out
    assert "Failed this run: 6" in out


def test_a_missing_corpus_index_exits_nonzero_instead_of_passing_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _corpus(tmp_path)
    (tmp_path / "corpus" / INDEX_KEY).unlink()

    code = enrich_corpus.main(["--local", str(tmp_path)], client=FakeDecisionApi().client())

    assert code == 2
    assert "Coverage: 100" not in capsys.readouterr().out


def test_a_prod_table_is_refused_without_the_owner_flag(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _corpus(tmp_path)

    code = enrich_corpus.main(["--table", "glean-recipes-prod", "--local", str(tmp_path)])

    assert code == 2
    assert "Refusing to run: glean-recipes-prod looks like a prod target" in capsys.readouterr().out


def test_a_prod_bucket_is_refused_too_because_blob_mode_writes_there(capsys: pytest.CaptureFixture) -> None:
    code = enrich_corpus.main(["--bucket", "glean-recipe-cache-prod-040396448697"])

    assert code == 2
    assert "looks like a prod target" in capsys.readouterr().out


def test_a_dry_run_may_look_at_a_prod_target_but_an_owner_flag_is_still_needed_to_write() -> None:
    enrich_corpus._refuse_remote("glean-recipes-prod", None, i_am_the_owner=False, writes=False)
    enrich_corpus._refuse_remote("glean-recipes-prod", None, i_am_the_owner=True)

    with pytest.raises(enrich_corpus.OwnerApprovalError):
        enrich_corpus._refuse_remote("glean-recipes-prod", None, i_am_the_owner=False)


@pytest.mark.parametrize("flag", ["--tab", "--i-am", "--loc"])
def test_an_abbreviated_flag_is_rejected_instead_of_expanding(tmp_path: Path, flag: str) -> None:
    """`--tab` must not quietly become `--table`: that is how a wrapper that refuses `--table` gets walked past."""
    _corpus(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        enrich_corpus.main(["--local", str(tmp_path), "--local-only", flag, "x"])

    assert exit_info.value.code == 2


@pytest.mark.parametrize(
    "args",
    [
        ["--local", "{tmp}", "--table", "glean-recipes-dev"],
        ["--bucket", "some-bucket"],
        ["--local", "{tmp}", "--i-am-the-owner"],
        ["--table", "glean-recipes-dev", "--bucket", "some-bucket"],
    ],
)
def test_local_only_refuses_a_remote_store_outright(
    tmp_path: Path, capsys: pytest.CaptureFixture, args: list[str]
) -> None:
    """What `make enrich-corpus` passes: no table, no bucket, no owner flag — not even for a dry run."""
    _corpus(tmp_path)

    code = enrich_corpus.main([arg.format(tmp=tmp_path) for arg in ["--local-only", "--dry-run", *args]])

    assert code == 2
    assert "Refusing to run: --local-only refuses" in capsys.readouterr().out


def test_local_only_on_its_own_runs_the_local_corpus(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _corpus(tmp_path)

    code = enrich_corpus.main(["--local", str(tmp_path), "--local-only", "--dry-run"])

    assert code == 0
    assert "Dry run: 2 recipes would be asked" in capsys.readouterr().out


@pytest.mark.parametrize(
    "args",
    ["--table glean-recipes-dev", "--bucket some-bucket", "--i-am-the-owner", "--dry-run --table glean-recipes-prod"],
)
def test_the_make_target_refuses_to_be_pointed_anywhere_but_the_local_corpus(args: str) -> None:
    """`make enrich-corpus` is the dev loop: no passthrough may select a remote table or bucket."""
    if shutil.which("make") is None:
        pytest.skip("make is not installed here")

    done = _make("enrich-corpus", f"ENRICH_ARGS={args}")

    assert done.returncode == 2
    assert "fills the local corpus only" in done.stdout + done.stderr
    assert "scripts/enrich_corpus.py --local" not in done.stdout  # it never got as far as running the CLI


def test_the_make_target_still_passes_run_options_through() -> None:
    if shutil.which("make") is None:
        pytest.skip("make is not installed here")

    done = _make("-n", "enrich-corpus", "ENRICH_ARGS=--dry-run --limit 2")

    assert done.returncode == 0
    assert "scripts/enrich_corpus.py --local .cache/glean_recipe_cache --local-only --dry-run --limit 2" in done.stdout


def _make(*args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).parents[3]  # the repo root, where the Makefile is
    make = shutil.which("make")
    assert make is not None  # the caller skipped when make is missing
    return subprocess.run(  # noqa: S603 - a fixed argv, and the binary is resolved above
        [make, "-C", str(root), *args], capture_output=True, text=True, check=False
    )


def test_an_unknown_enricher_is_refused_and_the_known_ones_are_named(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _corpus(tmp_path)

    code = enrich_corpus.main(["--local", str(tmp_path), "--dry-run", "--enricher", "attributes"])

    assert code == 2
    assert "no enricher called attributes; this build has: dietary" in capsys.readouterr().out


def test_the_enricher_filter_asks_only_that_enricher(tmp_path: Path) -> None:
    _corpus(tmp_path)
    api = FakeDecisionApi()

    code = enrich_corpus.main(["--local", str(tmp_path), "--enricher", "dietary"], client=api.client())

    assert code == 0
    assert set(api.requests[0]["questions"]) == {f"dietary:{flag}" for flag in _flags()}


def test_a_limit_asks_about_the_first_recipes_only(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _corpus(tmp_path)
    api = FakeDecisionApi()

    code = enrich_corpus.main(["--local", str(tmp_path), "--limit", "1"], client=api.client())

    assert code == 1  # the gate judges the whole corpus, and one recipe is left
    assert [request["state"]["recipe_title"] for request in api.requests] == ["Pesto Pasta"]
    assert "rec_tomato" in capsys.readouterr().out


def test_a_run_without_an_api_key_says_which_variable_to_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    _corpus(tmp_path)

    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        enrich_corpus.main(["--local", str(tmp_path)])


def _flags() -> tuple[str, ...]:
    from glean.recipes.enrichment.dietary import DIETARY_FLAGS  # noqa: PLC0415

    return DIETARY_FLAGS


def _corpus(tmp_path: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(BlobCorpusBackend(_blobs(tmp_path)))
    _save(corpus, "rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"])
    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])
    return corpus


def _blobs(tmp_path: Path):
    from glean.recipe_api.blob_store import FilesystemBlobStore  # noqa: PLC0415

    return FilesystemBlobStore(tmp_path / "corpus")


def _save(corpus: RecipeCorpusStore, external_id: str, title: str, ingredients: list[str]) -> None:
    corpus.save(
        StoredRecipe(
            external_id=external_id,
            title=title,
            ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
        )
    )
