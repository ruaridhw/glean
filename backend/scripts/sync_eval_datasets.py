#!/usr/bin/env python3
"""Push local eval fixture files to LangSmith datasets (one-way: git -> LangSmith)."""

from __future__ import annotations

import json
from pathlib import Path

from langsmith import Client

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "evals" / "fixtures"

DATASETS = {
    "receipt_scan.json": "glean-receipt-scan",
    "suggestions.json": "glean-suggestions",
    "recipe_import.json": "glean-recipe-import",
}


def sync_dataset(client: Client, fixture_path: Path, dataset_name: str) -> None:
    examples = json.loads(fixture_path.read_text())

    # Delete existing dataset if it exists, then recreate
    try:
        existing = client.read_dataset(dataset_name=dataset_name)
        client.delete_dataset(dataset_id=existing.id)
        print(f"  Deleted existing dataset: {dataset_name}")
    except Exception:
        pass

    dataset = client.create_dataset(dataset_name=dataset_name)
    print(f"  Created dataset: {dataset_name}")

    for example in examples:
        client.create_example(
            inputs=example["input"],
            outputs=example.get("expected", {}),
            dataset_id=dataset.id,
        )
    print(f"  Uploaded {len(examples)} examples")


def main() -> None:
    client = Client()
    print("Syncing eval datasets to LangSmith...")
    for filename, dataset_name in DATASETS.items():
        fixture_path = FIXTURES_DIR / filename
        if not fixture_path.exists():
            print(f"  Skipping {filename}: file not found")
            continue
        print(f"\n{filename} -> {dataset_name}")
        sync_dataset(client, fixture_path, dataset_name)
    print("\nDone.")


if __name__ == "__main__":
    main()
