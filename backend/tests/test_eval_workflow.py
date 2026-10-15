from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import SecretStr

from glean.llm import Feature, LLMRouter
from tests.integration.evals.conftest import _eval_model_id_for

if TYPE_CHECKING:
    import pytest

WORKFLOW = Path(__file__).parent.parent.parent / ".github" / "workflows" / "llm-evals.yml"
CHOSEN_MODEL = "custom/model-chosen-at-dispatch"


class TestLlmEvalsWorkflow:
    def test_model_chosen_at_dispatch_is_the_model_the_evals_use(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GLEAN_EVAL_MODEL", raising=False)
        job_env = yaml.safe_load(WORKFLOW.read_text())["jobs"]["eval"]["env"]
        for name, value in job_env.items():
            monkeypatch.setenv(name, str(value).replace("${{ inputs.model }}", CHOSEN_MODEL))

        model_id = _eval_model_id_for(Feature.RECEIPT_SCAN, LLMRouter(api_key=SecretStr("test-key")))

        assert model_id == CHOSEN_MODEL
