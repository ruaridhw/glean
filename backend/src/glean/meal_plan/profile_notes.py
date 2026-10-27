"""Which of the agent's profile notes the household is shown (V15, spec §6.4 "Feedback into the profile").

A `propose` action may carry `profile_notes`: short facts the agent inferred, each naming its evidence. The
household sees them as "Glean noted" and Keeps or dismisses each; nothing reaches the profile without a Keep.
`kept_notes` is the rule the graph applies before a note is written into the proposal:

- one line: runs of whitespace, newlines and tabs included, become one space, and the ends are trimmed;
- then at most `MAX_PROFILE_NOTE_CHARS` code points (the unit the app clips by), never empty, and with no control
  or format character left in it (Unicode Cc, Cf: escapes, zero-width and direction marks), since a kept note
  goes back into future prompts;
- no repeats, compared case-insensitively with runs of whitespace as one space, and none the household's profile
  already holds or has dismissed (`known_notes`);
- its evidence must exist in this session (`SessionEvidence`): at least `MIN_RATED_COOKS` distinct rated corpus
  recipes in the history window, an answered
  question (V11), or a screened swap note (V10);
- at most `MAX_PROFILE_NOTES`, the first that pass. A swap (V10) may add notes resting on its own screened
  swap note, merged after the proposal's and within the same total.

A note that fails is dropped, never repaired, and counted by reason for the session's log.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from glean.meal_plan.schemas import NoteEvidence, ProfileNote

if TYPE_CHECKING:
    from collections.abc import Iterable

    from glean.meal_plan.schemas import MealPlanRequest

MAX_PROFILE_NOTES = 3
MAX_PROFILE_NOTE_CHARS = 120
# One thumb is not a pattern: a rating note needs at least this many distinct rated corpus recipes in the window.
MIN_RATED_COOKS = 2
# Control and format characters: nothing a household would type in a one-line note, and a way to hide text.
_UNPRINTABLE = frozenset({"Cc", "Cf"})


@dataclass(frozen=True)
class SessionEvidence:
    """What this session holds that a note may rest on."""

    rated: bool
    answered: bool
    swap_note: bool

    def has(self, evidence: NoteEvidence) -> bool:
        return {
            NoteEvidence.RATING: self.rated,
            NoteEvidence.ANSWER: self.answered,
            NoteEvidence.SWAP_NOTE: self.swap_note,
        }[evidence]


def note_key(text: str) -> str:
    """What two notes are compared by: case-folded, with runs of whitespace as one space."""
    return " ".join(text.split()).casefold()


def known_notes(request: MealPlanRequest) -> list[str]:
    """The note texts the household's profile already holds or has dismissed, so the planner does not repeat them.

    The profile's `notes` and `dismissed_notes` reach the backend with the session request's `profile`. Until the
    request carries one this is empty, and only the app's own check (it hides a note its profile already has)
    stops a repeat.
    """
    return []


def kept_notes(
    notes: Iterable[ProfileNote],
    evidence: SessionEvidence,
    *,
    known: Iterable[str] = (),
    limit: int = MAX_PROFILE_NOTES,
) -> tuple[list[ProfileNote], dict[str, int]]:
    """The notes the household may see, at most *limit*, and how many were dropped for each reason."""
    kept: list[ProfileNote] = []
    seen: set[str] = set()
    held = {note_key(text) for text in known}
    dropped: Counter[str] = Counter()
    for note in notes:
        text = " ".join(note.text.split())
        reason = None
        if not text:
            reason = "empty"
        elif any(unicodedata.category(char) in _UNPRINTABLE for char in text):
            reason = "invalid"
        elif len(text) > MAX_PROFILE_NOTE_CHARS:
            reason = "too_long"
        elif note_key(text) in seen:
            reason = "duplicate"
        elif note_key(text) in held:
            reason = "known"
        elif not evidence.has(note.evidence):
            reason = "no_evidence"
        elif len(kept) >= limit:
            reason = "over_limit"
        if reason is not None:
            dropped[reason] += 1
            continue
        seen.add(note_key(text))
        kept.append(note.model_copy(update={"text": text}))
    return kept, dict(dropped)
