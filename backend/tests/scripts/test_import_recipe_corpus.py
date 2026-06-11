from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from scripts import import_recipe_corpus

from glean.recipes.offline import OfflineRecipeImportResult

if TYPE_CHECKING:
    from pathlib import Path


def test_read_jobs_file_supports_name_and_url(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.csv"
    jobs_file.write_text(
        "name,url\n"
        "Chicken Enchiladas with Creamy Green Chile Sauce,"
        "https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/\n"
        "Noodle Soup,https://recipes.example.test/recipes/noodle-soup-abc123\n"
    )

    jobs = import_recipe_corpus.read_jobs_file(jobs_file)

    assert [(job.name, job.url) for job in jobs] == [
        (
            "Chicken Enchiladas with Creamy Green Chile Sauce",
            "https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/",
        ),
        ("Noodle Soup", "https://recipes.example.test/recipes/noodle-soup-abc123"),
    ]


def test_read_jobs_file_rejects_provider_column(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.csv"
    jobs_file.write_text("provider,name,url\nweb,Noodle Soup,https://recipes.example.test/recipes/noodle-soup\n")

    with pytest.raises(ValueError, match="provider"):
        import_recipe_corpus.read_jobs_file(jobs_file)


def test_run_jobs_delegates_to_offline_url_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    def fake_import_offline_recipes(**kwargs: object) -> list[OfflineRecipeImportResult]:
        calls.append(kwargs)
        return [
            OfflineRecipeImportResult(
                name="Noodle Soup",
                status="imported",
                source_url="https://recipes.example.test/recipes/noodle-soup-abc123",
                recipe_id="260cca35d612aef7",
            )
        ]

    monkeypatch.setattr(import_recipe_corpus, "import_offline_recipes", fake_import_offline_recipes)
    jobs = [
        import_recipe_corpus.CorpusImportJob(
            name="Noodle Soup",
            url="https://recipes.example.test/recipes/noodle-soup-abc123",
        )
    ]
    model = object()
    corpus = MagicMock()
    manifest_path = tmp_path / "manifest.jsonl"

    results = import_recipe_corpus.run_jobs(
        jobs,
        model=model,
        corpus=corpus,
        manifest_path=manifest_path,
        rate_limit_seconds=0.0,
    )

    assert [result.status for result in results] == ["imported"]
    assert calls == [
        {
            "jobs": jobs,
            "model": model,
            "corpus": corpus,
            "manifest_path": manifest_path,
            "rate_limit_seconds": 0.0,
        }
    ]
