from __future__ import annotations

import statistics
import time

from glean.recipes.search_index import RecipeSearchIndex, RecipeSummary, dumps_summaries, loads_summaries


def test_search_matches_word_prefixes_in_title() -> None:
    index = RecipeSearchIndex(
        [
            _summary("rec_1", title="Chicken Tikka Masala"),
            _summary("rec_2", title="Beef Chilli"),
        ]
    )

    results, total = index.search(q="chick")

    assert [summary.external_id for summary in results] == ["rec_1"]
    assert total == 1


def test_search_matches_ingredient_names() -> None:
    index = RecipeSearchIndex(
        [
            _summary("rec_1", title="Weeknight Curry", ingredient_names=["chickpeas", "spinach"]),
            _summary("rec_2", title="Beef Chilli", ingredient_names=["beef mince"]),
        ]
    )

    results, _ = index.search(q="spinach")

    assert [summary.title for summary in results] == ["Weeknight Curry"]


def test_search_ranks_title_matches_above_ingredient_matches() -> None:
    index = RecipeSearchIndex(
        [
            _summary("rec_1", title="Pasta Bake", ingredient_names=["chicken breast"]),
            _summary("rec_2", title="Chicken Pie", ingredient_names=["puff pastry"]),
        ]
    )

    results, total = index.search(q="chicken")

    assert [summary.title for summary in results] == ["Chicken Pie", "Pasta Bake"]
    assert total == 2


def test_search_requires_every_query_word() -> None:
    index = RecipeSearchIndex(
        [
            _summary("rec_1", title="Chicken Tikka Masala"),
            _summary("rec_2", title="Chicken Pie"),
        ]
    )

    results, _ = index.search(q="chicken tikka")

    assert [summary.title for summary in results] == ["Chicken Tikka Masala"]


def test_search_treats_fts_syntax_as_plain_words() -> None:
    index = RecipeSearchIndex([_summary("rec_1", title="Mac and Cheese")])

    results, _ = index.search(q='mac AND "cheese" OR NEAR(')

    assert results == []


def test_search_with_only_punctuation_matches_nothing() -> None:
    index = RecipeSearchIndex([_summary("rec_1", title="Mac and Cheese")])

    assert index.search(q="!!!") == ([], 0)


def test_search_without_query_lists_all_in_title_order() -> None:
    index = RecipeSearchIndex(
        [
            _summary("rec_1", title="spaghetti Carbonara"),
            _summary("rec_2", title="Baked Ziti"),
        ]
    )

    results, total = index.search()

    assert [summary.title for summary in results] == ["Baked Ziti", "spaghetti Carbonara"]
    assert total == 2


def test_search_filters_cuisine_case_insensitively() -> None:
    index = RecipeSearchIndex(
        [
            _summary("rec_1", title="Baked Ziti", cuisine="Italian"),
            _summary("rec_2", title="Tofu Tacos", cuisine="Mexican"),
        ]
    )

    results, total = index.search(cuisine="italian")

    assert [summary.title for summary in results] == ["Baked Ziti"]
    assert total == 1


def test_search_dietary_filter_requires_all_requested_flags() -> None:
    index = RecipeSearchIndex(
        [
            _summary("rec_1", title="Chickpea Curry", dietary_flags=["Vegan", "Gluten-Free"]),
            _summary("rec_2", title="Green Salad", dietary_flags=["Vegan"]),
        ]
    )

    results, _ = index.search(dietary="vegan, gluten-free")

    assert [summary.title for summary in results] == ["Chickpea Curry"]


def test_search_paginates_and_reports_full_total() -> None:
    index = RecipeSearchIndex([_summary(f"rec_{i}", title=f"Soup {i:02d}") for i in range(25)])

    results, total = index.search(q="soup", page=2, per_page=10)

    assert total == 25
    assert len(results) == 10


def test_lookup_by_id_and_source_url() -> None:
    summary = _summary("rec_1", title="Soup", source_url="https://example.com/soup")
    index = RecipeSearchIndex([summary])

    assert index.by_id("rec_1") == summary
    assert index.by_source_url("https://example.com/soup") == summary
    assert index.by_id("missing") is None
    assert index.by_source_url("https://example.com/other") is None


def test_summaries_round_trip_through_jsonl_and_skip_bad_lines() -> None:
    summaries = [_summary("rec_2", title="B"), _summary("rec_1", title="A")]

    text = dumps_summaries(summaries) + "{not json\n\n"

    assert [summary.external_id for summary in loads_summaries(text)] == ["rec_1", "rec_2"]


def test_warm_search_over_5k_recipes_is_fast() -> None:
    words = ["chicken", "beef", "tofu", "pasta", "curry", "salad", "soup", "pie", "taco", "risotto"]
    index = RecipeSearchIndex(
        [
            _summary(
                f"rec_{i}",
                title=f"{words[i % 10].title()} with {words[(i * 7) % 10]} number {i}",
                ingredient_names=[words[(i * 3) % 10], "onion", "garlic", "olive oil"],
                cuisine=["Italian", "Mexican", "Indian"][i % 3],
            )
            for i in range(5000)
        ]
    )
    index.search(q="chicken")

    timings = []
    for query in ["chick", "beef pie", "curry", "tofu taco", "onion"]:
        start = time.perf_counter()
        index.search(q=query, cuisine="italian")
        timings.append(time.perf_counter() - start)

    assert statistics.median(timings) < 0.05


def _summary(
    external_id: str,
    *,
    title: str,
    source_url: str | None = None,
    cuisine: str | None = None,
    dietary_flags: list[str] | None = None,
    ingredient_names: list[str] | None = None,
) -> RecipeSummary:
    return RecipeSummary(
        external_id=external_id,
        key=f"{external_id}.json",
        title=title,
        source_url=source_url,
        cuisine=cuisine,
        dietary_flags=dietary_flags or [],
        ingredient_names=ingredient_names or [],
    )
