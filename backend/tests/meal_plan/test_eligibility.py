from __future__ import annotations

from datetime import UTC, datetime, timedelta

from glean.meal_plan.eligibility import CookedMeal, apply_recency_floor, recency_penalty

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
