"""Turn an eval judge rubric into a decision-model `score` question without rewording it."""

from __future__ import annotations

import re

from glean.decisions import ScoreQuestion

_LEVEL = re.compile(r"^([1-5]) = (.+)$", re.MULTILINE)


def rubric_score_question(rubric: str) -> ScoreQuestion:
    """The rubric's levels, worst first, as the ordered criteria of one `score` question."""
    matches = list(_LEVEL.finditer(rubric))
    if [match.group(1) for match in matches] != ["5", "4", "3", "2", "1"]:
        raise ValueError("A rubric needs five levels, written 5 down to 1")
    instructions = rubric[: matches[0].start()].strip()
    return ScoreQuestion(instructions=instructions, criteria=[match.group(2) for match in reversed(matches)])
