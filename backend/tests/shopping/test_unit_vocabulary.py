from __future__ import annotations

import re
from pathlib import Path

from glean.shopping.schemas import ShoppingUnit

_DART_UNITS = Path(__file__).parents[3] / "app" / "lib" / "data" / "util" / "unit_normalization.dart"


def test_backend_shopping_units_match_the_mobile_owned_vocabulary() -> None:
    declaration = re.search(r"const List<String> shoppingUnits = <String>\[(.*?)\];", _DART_UNITS.read_text(), re.S)
    assert declaration, "shoppingUnits not found in unit_normalization.dart"

    mobile_units = re.findall(r"'([^']+)'", declaration.group(1))

    assert mobile_units == [unit.value for unit in ShoppingUnit]
