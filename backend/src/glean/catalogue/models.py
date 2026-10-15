from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from glean.catalogue.groups import GROUPS, Form, GroupId, Kind, StockUnit, TrackingMode
from glean.catalogue.sections import Section, section_for


class Source(StrEnum):
    SEED = "seed"
    LLM = "llm"


def name_key(name: str) -> str:
    """The key a name is matched on: case-folded, trimmed, inner whitespace collapsed."""
    return " ".join(name.casefold().split())


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name_key(name)).strip("-")


class ItemOverrides(BaseModel):
    """Per-item changes to the rules its group would give it."""

    model_config = ConfigDict(frozen=True)

    tracking_mode: TrackingMode | None = Field(default=None, description="Overrides the group's tracking mode.")
    stock_unit: StockUnit | None = Field(default=None, description="Overrides the group's stock unit.")
    unopened_shelf_life_days: int | None = Field(
        default=None, gt=0, description="Overrides the unopened shelf life the group gives for the item's form."
    )
    once_opened_shelf_life_days: int | None = Field(
        default=None, gt=0, description="Overrides the once-opened shelf life the group gives for the item's form."
    )


class CatalogueItem(BaseModel):
    """An ingredient or household item. Its kind and default rules come from its ingredient group."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, description="Stable id, unique within the catalogue. Never reused or replaced.")
    name: str = Field(min_length=1, description="The canonical name.")
    aliases: tuple[str, ...] = Field(default=(), description="Other names that mean the same item.")
    group: GroupId = Field(description="The ingredient group the item takes its default rules from.")
    form: Form = Field(description="The form the ingredient is sold and kept in. Required: never defaulted.")
    overrides: ItemOverrides = Field(default=ItemOverrides(), description="Per-item changes to the group's rules.")
    former_ids: tuple[Annotated[str, StringConstraints(min_length=1)], ...] = Field(
        default=(),
        description="Ids of items merged into this one. A device resolves a former id, and any household override "
        "keyed on it, to this item.",
    )
    density_g_per_ml: float | None = Field(default=None, gt=0, description="Density in g/ml, where known.")
    source: Source = Field(description="Whether the item came from the seed or was added provisionally by an LLM.")

    @field_validator("aliases")
    @classmethod
    def _trim_aliases(cls, aliases: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(alias.strip() for alias in aliases)

    @model_validator(mode="after")
    def _check_form_and_stock_unit(self) -> CatalogueItem:
        rules = GROUPS[self.group]
        if rules.has_forms and self.form is Form.NOT_APPLICABLE:
            raise ValueError(f"{self.group.value} needs an explicit form")
        if self.form not in rules.allowed_forms:
            raise ValueError(f"{self.group.value} does not allow form {self.form.value}")
        if self.tracking_mode is TrackingMode.COUNTED and self.stock_unit is None:
            raise ValueError(f"{self.name}: a counted item needs a stock unit")
        return self

    @property
    def kind(self) -> Kind:
        return GROUPS[self.group].kind

    @property
    def tracking_mode(self) -> TrackingMode:
        return self.overrides.tracking_mode or GROUPS[self.group].tracking_mode

    @property
    def stock_unit(self) -> StockUnit | None:
        if self.tracking_mode is not TrackingMode.COUNTED:
            return None
        return self.overrides.stock_unit or GROUPS[self.group].stock_unit

    @property
    def unopened_shelf_life_days(self) -> int | None:
        """Days the item keeps unopened. None means no shelf life: it never expires."""
        return self.overrides.unopened_shelf_life_days or GROUPS[self.group].unopened_shelf_life_days[self.form]

    @property
    def once_opened_shelf_life_days(self) -> int | None:
        """Days the item keeps once opened. None where opening makes no difference or the item never expires."""
        return self.overrides.once_opened_shelf_life_days or GROUPS[self.group].once_opened_shelf_life_days[self.form]

    @property
    def section(self) -> Section:
        return section_for(self.group, self.form)
