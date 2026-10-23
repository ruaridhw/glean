from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from glean.meal_plan.schemas import (
    MAX_COOKED_HISTORY_ITEMS,
    MAX_COOKED_NOTE_LENGTH,
    CookedHistoryItem,
    MealPlanRequest,
)


def test_a_cooked_at_without_an_offset_is_read_as_utc() -> None:
    # The app always sends a UTC instant; an older build's local wall clock is read as UTC rather than
    # being rejected, so a request never fails over a missing offset.
    item = CookedHistoryItem(recipe_id="rec_a", title="A stew", cooked_at="2026-10-05T18:30:00")

    assert item.cooked_at == datetime(2026, 10, 5, 18, 30, tzinfo=UTC)


def test_a_cooked_at_with_an_offset_keeps_its_instant() -> None:
    item = CookedHistoryItem(recipe_id="rec_a", title="A stew", cooked_at="2026-10-05T18:30:00-07:00")

    assert item.cooked_at == datetime(2026, 10, 6, 1, 30, tzinfo=UTC)


def test_a_naive_cooked_at_after_normalisation_is_never_naive() -> None:
    item = CookedHistoryItem(title="A stew", cooked_at=datetime(2026, 10, 5, 18, 30))

    assert item.cooked_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize("rating", ["up", "down"])
def test_a_rating_is_one_of_the_two_thumbs(rating: str) -> None:
    item = CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z", rating=rating)

    assert item.rating == rating


def test_an_unrecognised_rating_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z", rating="meh")


def test_a_cook_without_a_rating_or_a_note_is_accepted() -> None:
    item = CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z")

    assert item.rating is None
    assert item.note is None


def test_a_note_is_accepted_up_to_its_bound() -> None:
    item = CookedHistoryItem(
        title="A stew",
        cooked_at="2026-10-05T18:30:00Z",
        rating="down",
        note="x" * MAX_COOKED_NOTE_LENGTH,
    )

    assert item.note == "x" * MAX_COOKED_NOTE_LENGTH


def test_a_note_longer_than_its_bound_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CookedHistoryItem(
            title="A stew",
            cooked_at="2026-10-05T18:30:00Z",
            note="x" * (MAX_COOKED_NOTE_LENGTH + 1),
        )


def test_the_note_bound_counts_unicode_code_points() -> None:
    # The app counts the same unit, so a note that saves can never fail this validation. A family emoji is
    # several code points even though it is one grapheme, and "e + combining acute" is two code points for
    # one visible character: both are measured as code points, here and in the sheet.
    combining = "e\u0301" * 250  # 250 graphemes, 500 code points
    emoji = "\U0001f468\u200d\U0001f469\u200d\U0001f467"  # one grapheme, 5 code points

    assert len(combining) == MAX_COOKED_NOTE_LENGTH
    assert CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z", note=combining).note == combining
    assert len(emoji * 100) == MAX_COOKED_NOTE_LENGTH
    CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z", note=emoji * 100)

    with pytest.raises(ValidationError):
        CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z", note=combining + "e")


def test_the_history_bound_leaves_room_for_too_old_dislikes() -> None:
    # The app sends the twelve-week window plus the latest cook behind each thumbs down, so the bound covers
    # both parts; one row more is still refused.
    def request_with(count: int) -> MealPlanRequest:
        return MealPlanRequest(
            pantry=[],
            food_group_coverage={},
            purchase_tolerance=0.5,
            meals_per_week=1,
            max_active_time_mins=None,
            dietary_flags=[],
            cooked_history=[{"title": f"Meal {index}", "cooked_at": "2026-10-05T18:30:00Z"} for index in range(count)],
        )

    assert len(request_with(MAX_COOKED_HISTORY_ITEMS).cooked_history) == MAX_COOKED_HISTORY_ITEMS
    with pytest.raises(ValidationError):
        request_with(MAX_COOKED_HISTORY_ITEMS + 1)
