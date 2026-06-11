from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

_TITLE_SUFFIX_PATTERNS = (
    re.compile(r"\b\d+\s*(?:min|mins|minute|minutes)\b", re.IGNORECASE),
    re.compile(r"\bprep\b", re.IGNORECASE),
    re.compile(r"\bcook\b", re.IGNORECASE),
    re.compile(r"\bserves?\b", re.IGNORECASE),
    re.compile(r"\bservings?\b", re.IGNORECASE),
    re.compile(r"\bwin\b", re.IGNORECASE),
    re.compile(r"\bfree\b", re.IGNORECASE),
)
_NUTRITION_FIELD_KEYS = {
    "calories": ("calories",),
    "protein_g": ("protein", "proteinContent", "protein_g"),
    "carbohydrates_g": ("carbohydrates", "carbohydrateContent", "carbohydrates_g"),
    "fat_g": ("fat", "fatContent", "fat_g"),
    "fibre_g": ("dietaryFibre", "fiberContent", "fibre_g", "fiber_g"),
    "sugar_g": ("sugars", "sugarContent", "sugar_g"),
    "sodium_mg": ("sodium", "sodiumContent", "sodium_mg"),
}
_PUBLIC_TEXT_MARKS = str.maketrans({"®": "", "™": "", "℠": "", "©": ""})


def raw_string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return raw_string_value(value.get("text") or value.get("name"))
    if isinstance(value, list):
        return ", ".join(text for item in value if (text := raw_string_value(item)))
    return str(value).strip()


def normalise_public_text(value: Any) -> str:
    text = raw_string_value(value)
    if not text:
        return ""
    text = unescape(text).translate(str.maketrans({"½": "1/2", "¼": "1/4", "¾": "3/4"}))
    text = text.translate(_PUBLIC_TEXT_MARKS)
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_recipe_title(value: Any) -> str:
    title = normalise_public_text(value)
    parts = [part.strip() for part in title.split("|")]
    if len(parts) <= 1:
        return title

    suffixes = [part for part in parts[1:] if part]
    if suffixes and all(_looks_like_title_metadata_suffix(part) for part in suffixes):
        return parts[0]
    return title


def sane_import_time_mins(minutes: int | None) -> int | None:
    if minutes is None or minutes <= 0 or minutes >= 720:
        return None
    return minutes


def nutrition_values_from_mapping(raw_nutrition: Any) -> dict[str, float] | None:
    if not isinstance(raw_nutrition, dict):
        return None

    values: dict[str, float] = {}
    for output_key, input_keys in _NUTRITION_FIELD_KEYS.items():
        value = _first_numeric_value(raw_nutrition, input_keys, output_key=output_key)
        if value is not None:
            values[output_key] = value

    if not values:
        return None
    return values


def nutrition_values_from_embedded_next_data(html: str) -> dict[str, float] | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None:
        return None

    try:
        data = json.loads(script.get_text() or "")
    except json.JSONDecodeError:
        return None

    recipe = _nested_dict(data, "props", "pageProps", "recipe")
    if recipe is None:
        return None
    nested_nutrition = recipe.get("nutrition")
    if isinstance(nested_nutrition, dict):
        return nutrition_values_from_mapping(nested_nutrition)
    return nutrition_values_from_mapping(recipe)


def _looks_like_title_metadata_suffix(value: str) -> bool:
    return any(pattern.search(value) for pattern in _TITLE_SUFFIX_PATTERNS)


def _first_numeric_value(raw_nutrition: dict[str, Any], keys: tuple[str, ...], *, output_key: str) -> float | None:
    for key in keys:
        value = raw_nutrition.get(key)
        parsed = _numeric_value(value)
        if parsed is None:
            continue
        if output_key == "sodium_mg" and isinstance(value, str) and _uses_gram_unit(value):
            return parsed * 1000
        return parsed
    return None


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    if match := re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", value):
        return float(match.group().replace(",", ""))
    return None


def _uses_gram_unit(value: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z])g(?:rams?)?\b", value, flags=re.IGNORECASE))


def _nested_dict(data: Any, *keys: str) -> dict[str, Any] | None:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, dict) else None
