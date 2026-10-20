from __future__ import annotations

import json

from glean.catalogue.naming import NameRequest, NamingResponse, name_items
from tests.catalogue.normalise_fakes import FakeRouter


def test_the_request_carries_each_name_as_a_json_string_so_the_model_echoes_it_unchanged() -> None:
    # Live, flash-lite echoed a decorated "- name (group: X)" line back as the input, so nothing matched.
    router = FakeRouter(
        script=lambda schema, user: schema(names=[{"input": "Birthday Candles", "canonical_name": "birthday candles"}])
    )

    named = name_items([NameRequest(input="Birthday Candles", group="Household")], llm_router=router)

    assert named == {"Birthday Candles": "birthday candles"}
    prompt = router.calls[0]["user"]
    assert {"input": "Birthday Candles", "group": "Household"} in json.loads(prompt[prompt.index("[") :])
    assert router.calls[0]["schema"] is NamingResponse
