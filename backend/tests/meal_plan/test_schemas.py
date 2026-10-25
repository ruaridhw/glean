from __future__ import annotations

from datetime import UTC, datetime, timedelta

from glean.meal_plan.schemas import CookedHistoryItem


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
