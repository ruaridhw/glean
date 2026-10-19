from __future__ import annotations

import pytest

from glean.catalogue.groups import GroupId
from glean.receipts.service import NORMALISE_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT


@pytest.mark.parametrize("prompt", [NORMALISE_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT], ids=["describe_and_scan", "vision"])
def test_the_receipt_prompts_list_every_ingredient_group(prompt: str) -> None:
    for group in GroupId:
        assert group.value in prompt


@pytest.mark.parametrize("prompt", [NORMALISE_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT], ids=["describe_and_scan", "vision"])
def test_the_receipt_prompts_ask_for_the_group_and_name_the_legacy_category(prompt: str) -> None:
    assert "- ingredient_group:" in prompt
    assert "- category:" in prompt
