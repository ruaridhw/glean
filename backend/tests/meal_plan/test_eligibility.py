from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from glean.meal_plan.eligibility import CookedMeal, apply_recency_floor, recency_penalty, recipe_history

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _cooked(recipe_id: str | None, title: str, *, days_ago: float) -> CookedMeal:
    return CookedMeal(recipe_id=recipe_id, title=title, cooked_at=NOW - timedelta(days=days_ago))


def _floor(
    eligible_ids: list[str],
    cooked: list[CookedMeal],
    *,
    slots: int = 1,
    window_days: int | None = None,
) -> tuple[list[str], list[str], bool]:
    kwargs = {} if window_days is None else {"window_days": window_days}
    result = apply_recency_floor(
        eligible_ids,
        titles={recipe_id: recipe_id.replace("rec_", "").replace("_", " ").title() for recipe_id in eligible_ids},
        cooked=cooked,
        now=NOW,
        slots=slots,
        **kwargs,
    )
    return list(result.fresh), list(result.relaxed), result.relaxed_floor


def test_a_recipe_cooked_in_the_last_six_weeks_is_left_out() -> None:
    fresh, relaxed, relaxed_floor = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked("rec_a", "A", days_ago=10)],
    )

    assert fresh == ["rec_b", "rec_c", "rec_d"]
    assert relaxed == []
    assert relaxed_floor is False


def test_the_six_weeks_are_counted_back_from_now_not_from_the_last_cook() -> None:
    fresh, relaxed, _ = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked("rec_a", "A", days_ago=7 * 6 + 1)],
    )

    assert "rec_a" in fresh
    assert relaxed == []


def test_a_recipe_cooked_exactly_six_weeks_ago_is_still_recent() -> None:
    fresh, relaxed, _ = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked("rec_a", "A", days_ago=42)],
    )

    assert "rec_a" not in fresh
    assert relaxed == []


def test_only_the_most_recent_cook_decides_for_a_recipe_cooked_more_than_once() -> None:
    fresh, _, _ = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked("rec_a", "A", days_ago=80), _cooked("rec_a", "A", days_ago=20)],
    )

    assert "rec_a" not in fresh


def test_the_floor_relaxes_only_when_it_would_leave_fewer_than_three_per_slot() -> None:
    # Six recipes is not enough for two slots once one of them is left out; the other five are.
    fresh, relaxed, relaxed_floor = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d", "rec_e", "rec_f"],
        [_cooked("rec_a", "A", days_ago=3)],
        slots=2,
    )

    assert relaxed_floor is True
    assert fresh == ["rec_b", "rec_c", "rec_d", "rec_e", "rec_f"]
    assert relaxed == ["rec_a"]


def test_six_eligible_recipes_hold_the_floor_for_two_slots() -> None:
    fresh, relaxed, relaxed_floor = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d", "rec_e", "rec_f", "rec_g"],
        [_cooked("rec_a", "A", days_ago=3)],
        slots=2,
    )

    assert relaxed_floor is False
    assert len(fresh) == 6
    assert relaxed == []


def test_relaxed_recipes_come_back_least_preferred_last() -> None:
    # All three are inside the floor, so the penalty ties and the longest-ago cook is offered first.
    _, relaxed, _ = _floor(
        ["rec_a", "rec_b", "rec_c"],
        [
            _cooked("rec_a", "A", days_ago=3),
            _cooked("rec_b", "B", days_ago=40),
            _cooked("rec_c", "C", days_ago=20),
        ],
        slots=2,
    )

    assert relaxed == ["rec_b", "rec_c", "rec_a"]


def test_relaxed_ordering_follows_the_penalty_bands() -> None:
    # With a wider floor window the bands differ: weeks 7-9 (-3) hurt less than inside six weeks (-8).
    _, relaxed, _ = _floor(
        ["rec_a", "rec_b", "rec_c"],
        [
            _cooked("rec_a", "A", days_ago=20),
            _cooked("rec_b", "B", days_ago=60),
            _cooked("rec_c", "C", days_ago=45),
        ],
        slots=2,
        window_days=120,
    )

    assert relaxed == ["rec_b", "rec_c", "rec_a"]


def test_history_without_a_recipe_id_is_matched_by_title() -> None:
    fresh, _, _ = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked(None, "A", days_ago=5)],
    )

    assert "rec_a" not in fresh


def test_a_title_match_ignores_case_and_surrounding_space() -> None:
    fresh, _, _ = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked(None, "  a ", days_ago=5)],
        window_days=42,
    )

    assert "rec_a" not in fresh


def test_no_history_leaves_every_recipe_fresh() -> None:
    fresh, relaxed, relaxed_floor = _floor(["rec_a", "rec_b"], [])

    assert fresh == ["rec_a", "rec_b"]
    assert relaxed == []
    assert relaxed_floor is False


def test_a_wide_history_window_blocks_a_recipe_cooked_longer_ago() -> None:
    fresh, _, _ = _floor(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked("rec_a", "A", days_ago=100)],
        window_days=120,
    )

    assert "rec_a" not in fresh


def test_recency_penalty_follows_the_scorer_weights_table() -> None:
    assert recency_penalty(None) == 0.0
    assert recency_penalty(0) == -8.0
    assert recency_penalty(42) == -8.0
    assert recency_penalty(43) == -3.0
    assert recency_penalty(63) == -3.0
    assert recency_penalty(64) == -1.0
    assert recency_penalty(84) == -1.0
    assert recency_penalty(85) == 0.0


def _result(
    eligible_ids: list[str],
    cooked: list[CookedMeal],
    *,
    slots: int = 1,
    now: datetime = NOW,
):
    return apply_recency_floor(
        eligible_ids,
        titles={recipe_id: recipe_id.replace("rec_", "").replace("_", " ").title() for recipe_id in eligible_ids},
        cooked=cooked,
        now=now,
        slots=slots,
    )


def test_a_recent_title_only_cook_outranks_an_older_cook_matched_by_id() -> None:
    # The plan entry cooked yesterday lost its snapshot, so it only carries a title. Its id-matched
    # counterpart from ten weeks ago must not hide it.
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked("rec_a", "A", days_ago=70), _cooked(None, "A", days_ago=1)],
    )

    assert "rec_a" not in result.fresh
    assert result.days_since_cooked["rec_a"] == pytest.approx(1)


def test_an_older_title_only_cook_does_not_hide_a_recent_id_matched_one() -> None:
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked("rec_a", "A", days_ago=2), _cooked(None, "A", days_ago=70)],
    )

    assert "rec_a" not in result.fresh
    assert result.days_since_cooked["rec_a"] == pytest.approx(2)


def test_every_matched_recipe_carries_the_age_of_its_most_recent_cook() -> None:
    # Public so the scorer can call recency_penalty on it, fresh recipes included.
    result = _result(
        ["rec_a", "rec_b", "rec_c"],
        [_cooked("rec_a", "A", days_ago=10), _cooked("rec_b", "B", days_ago=100)],
    )

    assert result.days_since_cooked == {"rec_a": pytest.approx(10), "rec_b": pytest.approx(100)}


def test_a_recipe_never_cooked_has_no_age() -> None:
    result = _result(["rec_a", "rec_b", "rec_c", "rec_d"], [_cooked("rec_a", "A", days_ago=10)])

    assert "rec_b" not in result.days_since_cooked


def test_a_cook_stated_in_another_timezone_is_aged_from_its_instant_not_its_wall_clock() -> None:
    pacific = timezone(timedelta(hours=-7))
    cooked_at = (NOW - timedelta(days=41, hours=23)).astimezone(pacific)
    hour_short_of_the_floor = _result(["rec_a", "rec_b", "rec_c", "rec_d"], [_cooked_at("rec_a", "A", cooked_at)])

    assert "rec_a" not in hour_short_of_the_floor.fresh

    a_day_over = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_cooked_at("rec_a", "A", (NOW - timedelta(days=42, hours=1)).astimezone(pacific))],
    )

    assert "rec_a" in a_day_over.fresh


def test_a_naive_cooked_at_is_read_as_utc() -> None:
    naive = (NOW - timedelta(days=41, hours=23)).replace(tzinfo=None)

    result = _result(["rec_a", "rec_b", "rec_c", "rec_d"], [_cooked_at("rec_a", "A", naive)])

    assert result.days_since_cooked["rec_a"] == pytest.approx(41 + 23 / 24)


def _cooked_at(recipe_id: str, title: str, cooked_at: datetime) -> CookedMeal:
    return CookedMeal(recipe_id=recipe_id, title=title, cooked_at=cooked_at)


def test_repeated_cooks_mixing_naive_and_aware_datetimes_age_by_their_instants() -> None:
    # A restored backup can bring UTC-stamped rows in beside the app's own local ones, so one recipe's
    # cooks can arrive in either order with either kind of datetime.
    aware = NOW - timedelta(days=5)
    naive = (NOW - timedelta(days=9)).replace(tzinfo=None)

    for rows in ((aware, naive), (naive, aware)):
        result = _result(
            ["rec_a", "rec_b", "rec_c", "rec_d"],
            [_cooked_at("rec_a", "A", rows[0]), _cooked_at("rec_a", "A", rows[1])],
        )

        assert result.days_since_cooked["rec_a"] == pytest.approx(5)


def test_a_naive_title_only_cook_is_compared_with_an_aware_id_matched_one() -> None:
    aware_recent = _cooked_at("rec_a", "A", NOW - timedelta(days=5))
    naive_older = _cooked_at(None, "A", (NOW - timedelta(days=9)).replace(tzinfo=None))

    for rows in ((aware_recent, naive_older), (naive_older, aware_recent)):
        result = _result(["rec_a", "rec_b", "rec_c", "rec_d"], list(rows))

        assert result.days_since_cooked["rec_a"] == pytest.approx(5)


def _rated(recipe_id: str | None, title: str, *, days_ago: float, rating: str | None) -> CookedMeal:
    return CookedMeal(recipe_id=recipe_id, title=title, cooked_at=NOW - timedelta(days=days_ago), rating=rating)


def test_a_recipe_whose_latest_rating_is_thumbs_down_is_left_out() -> None:
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=10, rating="down")],
    )

    assert "rec_a" not in result.recipe_ids
    assert result.disliked == ("rec_a",)
    assert "rec_a" not in result.days_since_cooked


def test_thumbs_down_stays_out_when_the_floor_relaxes() -> None:
    # Two slots leave too few fresh recipes, so the floor gives way for the recently cooked ones. A
    # thumbs down is a hard constraint and does not come back with them.
    result = _result(
        ["rec_a", "rec_b", "rec_c"],
        [_rated("rec_a", "A", days_ago=10, rating="down"), _rated("rec_b", "B", days_ago=20, rating=None)],
        slots=2,
    )

    assert result.relaxed_floor is True
    assert result.relaxed == ("rec_b",)
    assert "rec_a" not in result.recipe_ids


def test_clearing_the_thumb_brings_the_recipe_back() -> None:
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=60, rating=None)],
    )

    assert "rec_a" in result.fresh
    assert result.disliked == ()


def test_a_thumbs_up_rating_never_excludes_a_recipe() -> None:
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=60, rating="up")],
    )

    assert "rec_a" in result.fresh
    assert result.latest_rating == {"rec_a": "up"}


def test_the_most_recent_rating_decides() -> None:
    changed_their_mind = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=60, rating="down"), _rated("rec_a", "A", days_ago=5, rating="up")],
    )

    assert "rec_a" not in changed_their_mind.disliked
    assert changed_their_mind.latest_rating == {"rec_a": "up"}

    went_off_it = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=60, rating="up"), _rated("rec_a", "A", days_ago=5, rating="down")],
    )

    assert "rec_a" not in went_off_it.recipe_ids


def test_cooking_again_without_rating_leaves_the_earlier_thumb_standing() -> None:
    # A later unrated cook is not a verdict: only clearing or flipping the thumb changes one.
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=20, rating="down"), _rated("rec_a", "A", days_ago=2, rating=None)],
    )

    assert "rec_a" not in result.recipe_ids


def test_a_title_only_cook_carries_its_rating_to_the_recipe_it_names() -> None:
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated(None, "  a ", days_ago=60, rating="down")],
    )

    assert "rec_a" not in result.recipe_ids
    assert result.disliked == ("rec_a",)


def test_a_thumbs_down_recipe_can_still_be_named_by_title_when_the_new_cook_has_an_id() -> None:
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated(None, "A", days_ago=60, rating="down"), _rated("rec_a", "A", days_ago=2, rating=None)],
    )

    assert "rec_a" not in result.recipe_ids


def test_a_thumbs_down_older_than_the_window_still_keeps_the_recipe_out() -> None:
    # The verdict does not age with the cook: twenty weeks on, the recipe is still not offered. The app sends
    # that old cook on its own for exactly this reason.
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=140, rating="down")],
    )

    assert "rec_a" not in result.recipe_ids
    assert "rec_a" not in result.days_since_cooked
    assert result.disliked == ("rec_a",)


def test_a_later_thumbs_up_cancels_an_older_thumbs_down() -> None:
    # "Latest rating" (CONTEXT.md) is the thumb on the most recent rated cook, whichever way it points, so a
    # household that changed its mind is offered the recipe again once the newer cook is the only input.
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=200, rating="down"), _rated("rec_a", "A", days_ago=100, rating="up")],
    )

    assert "rec_a" not in result.disliked
    assert result.latest_rating == {"rec_a": "up"}


def test_a_later_title_only_thumbs_up_cancels_an_older_id_matched_thumbs_down() -> None:
    # The same recipe, identified by id on the old cook and only by title on the new one, as the app can send
    # after a plan entry loses its corpus id snapshot.
    result = _result(
        ["rec_a", "rec_b", "rec_c", "rec_d"],
        [_rated("rec_a", "A", days_ago=200, rating="down"), _rated(None, "  a ", days_ago=100, rating="up")],
    )

    assert "rec_a" not in result.disliked


def test_the_history_lookup_reads_one_household_the_way_the_floor_does() -> None:
    # The scorer needs a cook's age and its latest thumb for the recipes it was offered, without deciding
    # anything about them: one seam for both, so the age the floor relaxed on is the age the scorer reads.
    titles = {"rec_a": "Lentil Bake", "rec_b": "Tofu Noodles", "rec_c": "Fish Pie"}
    cooked = [
        CookedMeal(recipe_id="rec_a", title="Lentil Bake", cooked_at=NOW - timedelta(days=50), rating="up"),
        # No recipe id: an older plan entry, matched by title.
        CookedMeal(recipe_id=None, title="  tofu   noodles ", cooked_at=NOW - timedelta(days=3), rating="down"),
        # A later unrated cook of the first recipe must not erase its thumb.
        CookedMeal(recipe_id="rec_a", title="Lentil Bake", cooked_at=NOW - timedelta(days=4)),
    ]

    history = recipe_history(["rec_a", "rec_b", "rec_c"], titles=titles, cooked=cooked, now=NOW)
    floor = apply_recency_floor(["rec_a", "rec_b", "rec_c", "rec_d"], titles=titles, cooked=cooked, now=NOW, slots=1)

    assert history.days_since_cooked == {"rec_a": 4.0, "rec_b": 3.0}
    assert history.latest_rating == {"rec_a": "up", "rec_b": "down"}
    assert dict(floor.days_since_cooked) == {"rec_a": 4.0}  # rec_b is thumbs down, so not eligible
    assert dict(floor.latest_rating) == {"rec_a": "up"}
    assert floor.disliked == ("rec_b",)


def test_a_recipe_the_history_never_mentions_has_no_age_and_no_rating() -> None:
    history = recipe_history(["rec_a"], titles={"rec_a": "Lentil Bake"}, cooked=[], now=NOW)

    assert history.days_since_cooked == {}
    assert history.latest_rating == {}
