"""Which of the agent's profile notes the household is shown (V15, spec §6.4 "Feedback into the profile").

A `propose` action may carry `profile_notes`: short facts the agent inferred, each naming its evidence. The
household sees them as "Glean noted" and Keeps or dismisses each; nothing reaches the profile without a Keep.
`kept_notes` is the rule the graph applies before a note is written into the proposal:

- trimmed, then at most `MAX_PROFILE_NOTE_CHARS` code points (the unit the app clips by), never empty;
- no repeats, compared case-insensitively with runs of whitespace as one space;
- its evidence must exist in this session (`SessionEvidence`): a rated cook in the history window, an answered
  question (V11), or a screened swap note (V10);
- at most `MAX_PROFILE_NOTES`, the first that pass.

A note that fails is dropped, never repaired, and counted by reason for the session's log.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from glean.meal_plan.schemas import NoteEvidence, ProfileNote

if TYPE_CHECKING:
    from collections.abc import Iterable

MAX_PROFILE_NOTES = 3
MAX_PROFILE_NOTE_CHARS = 120


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


def kept_notes(notes: Iterable[ProfileNote], evidence: SessionEvidence) -> tuple[list[ProfileNote], dict[str, int]]:
    """The notes the household may see, and how many were dropped for each reason."""
    kept: list[ProfileNote] = []
    seen: set[str] = set()
    dropped: Counter[str] = Counter()
    for note in notes:
        text = note.text.strip()
        reason = None
        if not text:
            reason = "empty"
        elif len(text) > MAX_PROFILE_NOTE_CHARS:
            reason = "too_long"
        elif note_key(text) in seen:
            reason = "duplicate"
        elif not evidence.has(note.evidence):
            reason = "no_evidence"
        elif len(kept) >= MAX_PROFILE_NOTES:
            reason = "over_limit"
        if reason is not None:
            dropped[reason] += 1
            continue
        seen.add(note_key(text))
        kept.append(note.model_copy(update={"text": text}))
    return kept, dict(dropped)
