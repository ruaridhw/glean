#!/usr/bin/env python3
"""Load the versioned catalogue seed into the DynamoDB catalogue table. Safe to re-run: unchanged items are skipped."""

from __future__ import annotations

import argparse

from glean.catalogue.dynamo_store import DynamoCatalogueStore
from glean.catalogue.seed import load_seed


def seed_catalogue(store: DynamoCatalogueStore) -> int:
    """Write the seed items that are missing or differ. Returns how many were written."""
    return store.seed(load_seed().items)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", required=True, help="DynamoDB table name, e.g. glean-catalogue-prod")
    parser.add_argument("--region", default="eu-west-2")
    args = parser.parse_args()
    written = seed_catalogue(DynamoCatalogueStore(args.table, region=args.region))
    print(f"Catalogue seed complete: {written} items written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
