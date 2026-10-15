from __future__ import annotations

from typing import Any

import pytest
from scripts import sync_eval_datasets


class FakeLangSmithClient:
    """Stands in for the LangSmith service, the only boundary this script crosses."""

    def __init__(self) -> None:
        self.datasets: dict[str, list[dict[str, Any]]] = {}

    def read_dataset(self, *, dataset_name: str) -> Any:
        raise LookupError(dataset_name)

    def create_dataset(self, *, dataset_name: str) -> Any:
        self.datasets[dataset_name] = []
        return type("Dataset", (), {"id": dataset_name})()

    def create_example(self, *, inputs: dict[str, Any], outputs: dict[str, Any], dataset_id: str) -> None:
        self.datasets[dataset_id].append({"inputs": inputs, "outputs": outputs})


class TestSyncEvalDatasets:
    def test_uploads_the_receipt_scan_fixture_from_its_real_location(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        client = FakeLangSmithClient()
        monkeypatch.setattr(sync_eval_datasets, "Client", lambda: client)

        sync_eval_datasets.main()

        assert len(client.datasets["glean-receipt-scan"]) > 0
        assert "Skipping" not in capsys.readouterr().out
