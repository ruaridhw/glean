"""Plain-parsing allergen classifier: no LLM, so the same page always gives the same facts."""

from __future__ import annotations

import re

from .models import AllergenFacts, Product

# Coconut, nutmeg and butternut never match: terms are whole words and the bare "nut" needs its own word boundary.
_TREE_NUT = (
    r"pine\s+nuts?|pine\s+kernels?|(?:brazils?|almonds?|cashews?|hazelnuts?|walnuts?|pecans?|pistachios?|macadamias?)"
    r"(?:\s+nuts?)?|nuts?"
)
_PEANUT = r"peanuts?|groundnuts?|monkey\s+nuts?|arachis"
_TERMS = re.compile(rf"\b(?:(?P<peanut>{_PEANUT})|(?P<tree>{_TREE_NUT}))\b", re.IGNORECASE)
_MAY_CONTAIN = re.compile(r"\bmay\s+contain\b|\btraces?\s+of\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.;\n]")


def _terms(text: str) -> tuple[list[str], list[str]]:
    tree, peanut = [], []
    for match in _TERMS.finditer(text):
        (peanut if match.group("peanut") else tree).append(re.sub(r"\s+", " ", match.group(0).lower()))
    return tree, peanut


def _split_warning(text: str) -> tuple[str, list[str]]:
    """The text before the first warning, and each warning clause (up to the end of its sentence)."""
    first = _MAY_CONTAIN.search(text)
    if first is None:
        return text, []
    warnings = []
    for match in _MAY_CONTAIN.finditer(text):
        end = _SENTENCE_END.search(text, match.end())
        warnings.append(text[match.start() : end.start() if end else len(text)])
    return text[: first.start()], warnings


def classify(product: Product) -> AllergenFacts:
    """Nuts and peanuts as ingredients, and (separately) in a 'may contain' warning on either text."""
    ingredients, ingredient_warnings = _split_warning(product.ingredients_text)
    _, allergy_warnings = _split_warning(product.allergy_text)
    tree, peanut = _terms(ingredients)
    warned_tree, warned_peanut, quotes = False, False, []
    for warning in [*ingredient_warnings, *allergy_warnings]:
        warning_tree, warning_peanut = _terms(warning)
        if warning_tree or warning_peanut:
            quotes.append(warning.strip())
        warned_tree = warned_tree or bool(warning_tree)
        warned_peanut = warned_peanut or bool(warning_peanut)
    return AllergenFacts(
        tree_nut_ingredients=tree,
        peanut_ingredients=peanut,
        may_contain_tree_nut=warned_tree,
        may_contain_peanut=warned_peanut,
        may_contain_quote="; ".join(dict.fromkeys(quotes)) or None,
    )
