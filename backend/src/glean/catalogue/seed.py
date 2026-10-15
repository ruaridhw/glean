from __future__ import annotations

import json
from importlib import resources

from pydantic import BaseModel, ConfigDict

from glean.catalogue.models import CatalogueItem, Source, slugify

_SEED_FILE = "seed_v1.json"


class SeedData(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    items: tuple[CatalogueItem, ...]


def load_seed() -> SeedData:
    """Read and validate the versioned seed file. Item ids are the slug of the canonical name."""
    raw = json.loads(resources.files("glean.catalogue").joinpath("data", _SEED_FILE).read_text(encoding="utf-8"))
    items = tuple(
        CatalogueItem.model_validate({**entry, "id": slugify(entry["name"]), "source": Source.SEED})
        for entry in raw["items"]
    )
    return SeedData(version=raw["version"], items=items)
