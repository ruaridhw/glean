from __future__ import annotations

import re
from typing import Any

from glean.recipes.import_normalization import normalise_public_text
from glean.recipes.stored import StoredIngredient

# Keep this aligned with mobile/src/normalization/units.ts and
# mobile/src/meals/presentation.ts. Recipe imports and mobile display need the
# same canonical unit vocabulary.
_MEASURE_UNITS = {
    "g": (1.0, "g"),
    "gram": (1.0, "g"),
    "grams": (1.0, "g"),
    "kg": (1000.0, "g"),
    "kilogram": (1000.0, "g"),
    "kilograms": (1000.0, "g"),
    "ml": (1.0, "ml"),
    "millilitre": (1.0, "ml"),
    "millilitres": (1.0, "ml"),
    "milliliter": (1.0, "ml"),
    "milliliters": (1.0, "ml"),
    "l": (1000.0, "ml"),
    "litre": (1000.0, "ml"),
    "litres": (1000.0, "ml"),
    "liter": (1000.0, "ml"),
    "liters": (1000.0, "ml"),
    "tsp": (1.0, "tsp"),
    "teaspoon": (1.0, "tsp"),
    "teaspoons": (1.0, "tsp"),
    "tbsp": (1.0, "tbsp"),
    "tablespoon": (1.0, "tbsp"),
    "tablespoons": (1.0, "tbsp"),
    "cm": (1.0, "cm"),
    "centimetre": (1.0, "cm"),
    "centimetres": (1.0, "cm"),
    "centimeter": (1.0, "cm"),
    "centimeters": (1.0, "cm"),
}
_COUNT_UNITS = {"unit", "units", "unit(s)"}
_PACKAGE_UNITS = {"pouch", "pouches", "sachet", "sachets", "sachet(s)", "pack", "packs", "packet", "packets"}
_CONTAINERS = {"can", "cans", "tin", "tins", "jar", "jars", "pouch", "pouches", "bottle", "bottles"}
_NUMBER_PATTERN = r"\d+(?:\.\d+)?|\d+/\d+"
_COMPACT_PREFIX_UNITS = {
    *_MEASURE_UNITS,
    *_COUNT_UNITS,
    *_PACKAGE_UNITS,
    "breast",
    "bulb",
    "bunch",
    "clove",
    "dash",
    "head",
    "knob",
    "leaf",
    "pinch",
    "rasher",
    "roll",
    "sheet",
    "slice",
    "sprig",
    "stalk",
    "stick",
    "thigh",
}
_COMPACT_PREFIX_UNIT_PATTERN = "|".join(
    re.escape(unit) for unit in sorted(_COMPACT_PREFIX_UNITS, key=len, reverse=True)
)


def parse_ingredient_text(raw: object) -> StoredIngredient | None:
    text = _normalise_label(raw)
    if not text:
        return None

    text = _normalise_compact_label(text)
    name, quantity, unit, preparation = _parse_label(text)
    return StoredIngredient(
        canonical_name=_capitalise_first(name),
        quantity=quantity,
        unit=unit,
        preparation=preparation,
    )


def _parse_label(text: str) -> tuple[str, float, str, str | None]:
    if parsed := _parse_package_measure(text):
        return parsed
    if parsed := _parse_suffix_measure_or_count(text):
        return parsed
    if parsed := _parse_measure_prefix(text):
        return parsed
    if parsed := _parse_count_or_package_prefix(text):
        return parsed
    return text, 1.0, "pcs", None


def _parse_package_measure(text: str) -> tuple[str, float, str, str | None] | None:
    if match := re.match(
        rf"^(?P<count>{_NUMBER_PATTERN})x\s+(?P<amount>{_NUMBER_PATTERN})\s*(?P<unit>[A-Za-z]+)\s+"
        rf"(?P<container>{'|'.join(sorted(_CONTAINERS))})\s+(?P<name>.+)$",
        text,
        flags=re.IGNORECASE,
    ):
        count = _parse_quantity(match.group("count"))
        amount = _parse_quantity(match.group("amount"))
        converted = _convert_measure(amount * count, match.group("unit"))
        if converted is None:
            return None
        quantity, unit = converted
        container = _singular_container(match.group("container"))
        return match.group("name").strip(), quantity, unit, f"{_format_quantity(count)} {_pluralise(container, count)}"

    if match := re.match(
        rf"^(?P<count>{_NUMBER_PATTERN})x\s+(?P<amount>{_NUMBER_PATTERN})\s*(?P<unit>[A-Za-z]+)\s+(?P<name>.+)$",
        text,
        flags=re.IGNORECASE,
    ):
        count = _parse_quantity(match.group("count"))
        amount = _parse_quantity(match.group("amount"))
        converted = _convert_measure(amount * count, match.group("unit"))
        if converted is None:
            return None
        quantity, unit = converted
        return match.group("name").strip(), quantity, unit, None

    return None


def _parse_measure_prefix(text: str) -> tuple[str, float, str, str | None] | None:
    if match := re.match(
        rf"^(?P<quantity>{_NUMBER_PATTERN})\s*(?P<unit>[A-Za-z]+)\s+(?P<name>.+)$",
        text,
        flags=re.IGNORECASE,
    ):
        converted = _convert_measure(_parse_quantity(match.group("quantity")), match.group("unit"))
        if converted is None:
            return None
        quantity, unit = converted
        return match.group("name").strip(), quantity, unit, None
    return None


def _parse_suffix_measure_or_count(text: str) -> tuple[str, float, str, str | None] | None:
    if match := re.match(
        rf"^(?P<name>.+?)\s+\((?P<amount>{_NUMBER_PATTERN})\s*(?P<unit>[A-Za-z]+)\)\s*"
        rf"(?:x(?P<count>{_NUMBER_PATTERN}))?$",
        text,
        flags=re.IGNORECASE,
    ):
        count = _parse_quantity(match.group("count")) if match.group("count") else 1.0
        amount = _parse_quantity(match.group("amount"))
        converted = _convert_measure(amount * count, match.group("unit"))
        if converted is None:
            return None
        quantity, unit = converted
        return match.group("name").strip(), quantity, unit, None

    if match := re.match(rf"^(?P<name>.+?)\s+x(?P<count>{_NUMBER_PATTERN})$", text, flags=re.IGNORECASE):
        return match.group("name").strip(), _parse_quantity(match.group("count")), "pcs", None

    return None


def _parse_count_or_package_prefix(text: str) -> tuple[str, float, str, str | None] | None:
    match = re.match(
        rf"^(?P<quantity>{_NUMBER_PATTERN})\s+(?P<unit>[A-Za-z()]+)\s+(?P<name>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        if count_match := re.match(rf"^(?P<quantity>{_NUMBER_PATTERN})\s+(?P<name>.+)$", text):
            return count_match.group("name").strip(), _parse_quantity(count_match.group("quantity")), "pcs", None
        return None

    quantity = _parse_quantity(match.group("quantity"))
    raw_unit = match.group("unit").lower()
    name = match.group("name").strip()
    if raw_unit in _COUNT_UNITS:
        return name, quantity, "pcs", None
    if raw_unit in _PACKAGE_UNITS:
        package = _singular_container(raw_unit.replace("(s)", ""))
        return name, quantity, "units", f"{_format_quantity(quantity)} {_pluralise(package, quantity)}"
    return f"{match.group('unit')} {name}".strip(), quantity, "pcs", None


def _normalise_compact_label(text: str) -> str:
    text = re.sub(rf"^(?P<quantity>{_NUMBER_PATTERN})tabtbsp\b", r"\g<quantity>tbsp", text, flags=re.IGNORECASE)
    if match := re.match(
        rf"^(?P<quantity>{_NUMBER_PATTERN})(?P<unit>{_COMPACT_PREFIX_UNIT_PATTERN})(?P<name>.+)$",
        text,
        flags=re.IGNORECASE,
    ):
        name = match.group("name")
        if name.startswith(" ") or name[:1].isupper():
            return f"{match.group('quantity')} {match.group('unit')} {name.strip()}"
    return text


def _convert_measure(quantity: float, raw_unit: str) -> tuple[float, str] | None:
    conversion = _MEASURE_UNITS.get(raw_unit.lower())
    if conversion is None:
        return None
    factor, unit = conversion
    return quantity * factor, unit


def _parse_quantity(value: str) -> float:
    if "/" not in value:
        return float(value)
    numerator, denominator = value.split("/", maxsplit=1)
    return float(numerator) / float(denominator)


def _normalise_label(raw: Any) -> str:
    return normalise_public_text(raw)


def _capitalise_first(value: str) -> str:
    value = value.strip()
    return f"{value[:1].upper()}{value[1:]}" if value else value


def _singular_container(value: str) -> str:
    value = value.lower().strip()
    return {"cans": "can", "tins": "tin", "jars": "jar", "pouches": "pouch", "bottles": "bottle"}.get(value, value)


def _pluralise(value: str, quantity: float) -> str:
    if quantity == 1:
        return value
    if value.endswith("ch"):
        return f"{value}es"
    return f"{value}s"


def _format_quantity(quantity: float) -> str:
    return str(int(quantity)) if quantity.is_integer() else str(quantity)
