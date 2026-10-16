"""Per-ingredient verdicts: how often products on a retailer's shelf carry tree nuts or peanuts."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from .classify import classify
from .retailers import ProductUnreadable, RetailerBlocked

if TYPE_CHECKING:
    from .cache import ProductCache
    from .models import Product
    from .retailers import RetailerReader


class Frequency(StrEnum):
    USUALLY = "usually"
    SOMETIMES = "sometimes"
    RARELY = "rarely"


class ContainsPolicy(BaseModel):
    """When an ingredient type 'contains' an allergen. A policy setting, not a fact about the products."""

    minimum: Frequency = Field(
        default=Frequency.USUALLY,
        description="The least frequent verdict that counts: 'usually' means most products list the allergen.",
    )
    may_contain_counts: bool = Field(
        default=False, description="Whether 'may contain' warnings count as well as listed ingredients."
    )


class Evidence(BaseModel):
    kind: Literal["ingredient", "may_contain"] = Field(description="Whether the quote is an ingredient or a warning.")
    url: str = Field(description="The product page the quote was read from.")
    product_name: str = Field(description="The product's name.")
    quote: str = Field(description="The text as the page prints it.")


class IngredientVerdict(BaseModel):
    ingredient: str = Field(description="The processed ingredient that was looked up, e.g. 'korma curry paste'.")
    status: Literal["resolved", "blocked", "not_found", "insufficient"] = Field(
        description="'resolved' when enough products were read; 'blocked' when a shop refused and nothing was read; "
        "'not_found' when no matching product had an ingredients list; 'insufficient' when too few pages could "
        "be read to say. Only 'resolved' carries frequencies."
    )
    retailer: str | None = Field(default=None, description="The retailer the products were read from.")
    products_read: int = Field(default=0, description="How many products with an ingredients list were read.")
    tree_nut_products: int = Field(default=0, description="Products listing a tree nut as an ingredient.")
    peanut_products: int = Field(default=0, description="Products listing peanut as an ingredient.")
    may_contain_products: int = Field(
        default=0, description="Products whose 'may contain' warning names nuts or peanuts."
    )
    tree_nut: Frequency | None = Field(default=None, description="How often a tree nut is an ingredient.")
    peanut: Frequency | None = Field(default=None, description="How often peanut is an ingredient.")
    may_contain: Frequency | None = Field(default=None, description="How often a 'may contain' warning names nuts.")
    evidence: list[Evidence] = Field(default_factory=list, description="The quoted text behind every count.")


def frequency(count: int, total: int) -> Frequency:
    """'usually' when more than half the products have it, 'sometimes' when some do, else 'rarely'."""
    if count == 0:
        return Frequency.RARELY
    return Frequency.USUALLY if count * 2 > total else Frequency.SOMETIMES


def is_unsafe(verdict: IngredientVerdict, policy: ContainsPolicy | None = None) -> bool | None:
    """Whether the ingredient contains a tree nut or peanut under `policy`; None when the shelf couldn't be read."""
    policy = policy or ContainsPolicy()
    if verdict.status != "resolved":
        return None
    found = (verdict.tree_nut, verdict.peanut, verdict.may_contain if policy.may_contain_counts else None)
    reached = {Frequency.USUALLY} if policy.minimum is Frequency.USUALLY else {Frequency.USUALLY, Frequency.SOMETIMES}
    return any(frequency in reached for frequency in found)


def _verdict(ingredient: str, retailer: str, products: list[Product]) -> IngredientVerdict:
    evidence: list[Evidence] = []
    tree = peanut = warned = 0
    for product in products:
        facts = classify(product)
        if facts.tree_nut_ingredients or facts.peanut_ingredients:
            evidence.append(
                Evidence(kind="ingredient", url=product.url, product_name=product.name, quote=product.ingredients_text)
            )
        if facts.may_contain_quote:
            evidence.append(
                Evidence(kind="may_contain", url=product.url, product_name=product.name, quote=facts.may_contain_quote)
            )
        tree += bool(facts.tree_nut_ingredients)
        peanut += bool(facts.peanut_ingredients)
        warned += facts.may_contain_tree_nut or facts.may_contain_peanut
    total = len(products)
    return IngredientVerdict(
        ingredient=ingredient,
        status="resolved",
        retailer=retailer,
        products_read=total,
        tree_nut_products=tree,
        peanut_products=peanut,
        may_contain_products=warned,
        tree_nut=frequency(tree, total),
        peanut=frequency(peanut, total),
        may_contain=frequency(warned, total),
        evidence=evidence,
    )


_GENERIC_WORDS = frozenset(
    {"paste", "pastes", "sauce", "sauces", "curry", "seasoning", "spice", "spices", "mix", "powder", "pot", "pots"}
)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold().replace("'", "").replace("\u2019", ""))


def _is_relevant(query: str, product_name: str) -> bool:
    """A hit is on topic when it names every distinctive word of the query: 'korma' in 'korma curry paste',
    and the brand in "Patak's korma paste", which narrows the read to that brand's products."""
    name = " ".join(_words(product_name))
    return all(word in name for word in _words(query) if word not in _GENERIC_WORDS)


def _read_products(reader: RetailerReader, query: str, n: int) -> list[Product]:
    products = []
    for ref in [ref for ref in reader.search(query) if _is_relevant(query, ref.name)][:n]:
        try:
            products.append(reader.read(ref))
        except ProductUnreadable:
            continue
    return products


def ground_truth(
    ingredient_name: str, n: int = 5, *, readers: list[RetailerReader], cache: ProductCache | None = None
) -> IngredientVerdict:
    """Read the top `n` products for `ingredient_name` and say how often they carry nuts or peanuts.

    Readers are tried in order; a blocked or empty one hands over to the next. Nothing is ever guessed.
    A cache hit costs no browser requests; blocked and empty reads are never cached.
    """
    blocked = False
    for reader in readers:
        products = cache.get(reader.name, ingredient_name, n) if cache else None
        if products is None:
            try:
                products = _read_products(reader, ingredient_name, n)
            except RetailerBlocked:
                blocked = True
                continue
            if products and cache:
                cache.put(reader.name, ingredient_name, n, products)
        if products:
            return _verdict(ingredient_name, reader.name, products)
    return IngredientVerdict(ingredient=ingredient_name, status="blocked" if blocked else "not_found")
