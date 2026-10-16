"""Per-ingredient verdicts: how often products on a retailer's shelf carry tree nuts or peanuts."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from .classify import classify
from .retailers import ProductUnreadable, RetailerBlocked

if TYPE_CHECKING:
    from .cache import ProductCache
    from .models import Product, ProductRef
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
    kind: Literal["ingredients", "may_contain", "unread"] = Field(
        description="'ingredients': a product read, quoted whether or not it lists a nut; 'may_contain': a warning, "
        "kept separate; 'unread': a matching product whose page could not be read."
    )
    url: str = Field(description="The product page the quote was read from.")
    product_name: str = Field(description="The product's name.")
    quote: str = Field(description="The text as the page prints it; empty for an unread product.")
    allergens: list[str] = Field(
        default_factory=list, description="The tree nut and peanut terms the ingredients list names, if any."
    )


class IngredientVerdict(BaseModel):
    ingredient: str = Field(description="The processed ingredient that was looked up, e.g. 'korma curry paste'.")
    status: Literal["resolved", "blocked", "not_found", "insufficient"] = Field(
        description="'resolved' when enough products were read; 'blocked' when a shop refused and nothing was read; "
        "'not_found' when no matching product had an ingredients list; 'insufficient' when too few pages could "
        "be read to say. Only 'resolved' carries frequencies."
    )
    retailer: str | None = Field(default=None, description="The retailer the products were read from.")
    products_read: int = Field(default=0, description="How many products with an ingredients list were read.")
    products_unread: int = Field(default=0, description="How many matching products' pages could not be read.")
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


def _unsafe(tree: int, peanut: int, warned: int, total: int, policy: ContainsPolicy) -> bool:
    reached = {Frequency.USUALLY} if policy.minimum is Frequency.USUALLY else {Frequency.USUALLY, Frequency.SOMETIMES}
    counts = [tree, peanut, *([warned] if policy.may_contain_counts else [])]
    return any(frequency(count, total) in reached for count in counts)


def is_unsafe(verdict: IngredientVerdict, policy: ContainsPolicy | None = None) -> bool | None:
    """Whether the ingredient contains a tree nut or peanut under `policy`; None when the shelf couldn't be read."""
    policy = policy or ContainsPolicy()
    if verdict.status != "resolved":
        return None
    found = (verdict.tree_nut, verdict.peanut, verdict.may_contain if policy.may_contain_counts else None)
    reached = {Frequency.USUALLY} if policy.minimum is Frequency.USUALLY else {Frequency.USUALLY, Frequency.SOMETIMES}
    return any(frequency in reached for frequency in found)


_MINIMUM_READ = 3


def _could_flip(tree: int, peanut: int, warned: int, read: int, unread: int, policy: ContainsPolicy) -> bool:
    """Whether the unread products could change the answer under `policy`: safe if none of them list or warn about
    a nut, unsafe if all of them do."""
    total = read + unread
    return _unsafe(tree, peanut, warned, total, policy) != _unsafe(
        tree + unread, peanut + unread, warned + unread, total, policy
    )


def _verdict(
    ingredient: str,
    retailer: str,
    products: list[Product],
    unread: list[ProductRef],
    *,
    minimum_read: int,
    policy: ContainsPolicy,
) -> IngredientVerdict:
    evidence: list[Evidence] = []
    tree = peanut = warned = 0
    for product in products:
        facts = classify(product)
        allergens = [*facts.tree_nut_ingredients, *facts.peanut_ingredients]
        evidence.append(
            Evidence(
                kind="ingredients",
                url=product.url,
                product_name=product.name,
                quote=product.ingredients_text,
                allergens=allergens,
            )
        )
        if facts.may_contain_quote:
            evidence.append(
                Evidence(kind="may_contain", url=product.url, product_name=product.name, quote=facts.may_contain_quote)
            )
        tree += bool(facts.tree_nut_ingredients)
        peanut += bool(facts.peanut_ingredients)
        warned += facts.may_contain_tree_nut or facts.may_contain_peanut
    evidence += [Evidence(kind="unread", url=ref.url, product_name=ref.name, quote="") for ref in unread]
    read, missed = len(products), len(unread)
    common = {
        "ingredient": ingredient,
        "retailer": retailer,
        "products_read": read,
        "products_unread": missed,
        "tree_nut_products": tree,
        "peanut_products": peanut,
        "may_contain_products": warned,
        "evidence": evidence,
    }
    if read < minimum_read or _could_flip(tree, peanut, warned, read, missed, policy):
        return IngredientVerdict(status="insufficient", **common)
    return IngredientVerdict(
        status="resolved",
        tree_nut=frequency(tree, read),
        peanut=frequency(peanut, read),
        may_contain=frequency(warned, read),
        **common,
    )


# What the ingredient is: a product must be this kind of thing, so "curry paste" never reads almond butter.
_KINDS = frozenset({"paste", "sauce", "seasoning", "mix", "powder", "marinade"})
# Other names shops give the same kind of product: UK tomato paste is sold as purée, stock paste as a stock pot.
_SAME_KIND = {"paste": frozenset({"paste", "puree", "marinade", "pot", "concentrate"})}
# Words that name the cuisine more than the product; they only matter when nothing else distinguishes the query.
_GENERIC_WORDS = frozenset({"curry", "spice", "pot"})
# Curry styles: "curry paste" asks for any of them, as in "Korma Spice Paste".
_CURRY_STYLES = frozenset(
    {"korma", "tikka", "masala", "madras", "jalfrezi", "balti", "rogan", "vindaloo", "bhuna", "pasanda", "tandoori"}
    | {"massaman", "rendang", "katsu", "biryani", "dhansak", "saag", "thai"}
)
# A kit that contains the paste is still the paste; a ready meal or snack is something else.
_NOT_THE_INGREDIENT = frozenset({"meal", "ready", "pie", "soup", "bake", "snack", "crisps"})


def _tokens(text: str) -> set[str]:
    """Whole lower-case words with apostrophes dropped and a plural 's' folded away."""
    plain = unicodedata.normalize("NFKD", text.casefold()).encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", plain.replace("'", ""))
    return {word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word for word in words}


def _is_relevant(query: str, product_name: str) -> bool:
    """A hit is the ingredient asked for: it names the query's kind ('paste') and every distinctive word ('korma',
    or the brand in "Patak's korma paste", which narrows the read to that brand), and isn't a ready meal.

    When a query has nothing distinctive ('curry paste') the cuisine word has to match too."""
    wanted, name = _tokens(query), _tokens(product_name)
    distinctive = wanted - _KINDS - _GENERIC_WORDS or wanted & _GENERIC_WORDS
    if distinctive == {"curry"} and not name & ({"curry"} | _CURRY_STYLES):
        return False
    if distinctive == {"curry"}:
        distinctive = set()
    kind_matches = all(name & _SAME_KIND.get(kind, {kind}) for kind in wanted & _KINDS)
    return kind_matches and distinctive <= name and not name & _NOT_THE_INGREDIENT


_SIZE = re.compile(r"x?\d+(?:x\d+)?(?:g|kg|ml|cl|l|pack)?")


def _names_exactly(query: str, product_name: str) -> bool:
    """The query names this very product: every significant word of the product's name is in the query
    (sizes and cuisine words aside), so "Patak's korma paste" names Patak's Korma Spice Paste 290g."""
    significant = {word for word in _tokens(product_name) - _GENERIC_WORDS if not _SIZE.fullmatch(word)}
    return significant <= _tokens(query)


def _read_products(reader: RetailerReader, query: str, n: int) -> tuple[list[Product], list[ProductRef]]:
    products, unread = [], []
    seen: set[str] = set()
    for ref in [ref for ref in reader.search(query) if _is_relevant(query, ref.name)][:n]:
        if ref.url in seen:
            continue
        seen.add(ref.url)
        try:
            products.append(reader.read(ref))
        except ProductUnreadable:
            unread.append(ref)
    return products, unread


def _judge(
    query: str,
    retailer: str,
    products: list[Product],
    unread: list[ProductRef],
    minimum_read: int,
    policy: ContainsPolicy,
) -> IngredientVerdict:
    """A named product is judged by its own ingredients alone, and one product is enough for it."""
    exact = [product for product in products if _names_exactly(query, product.name)]
    if exact:
        return _verdict(query, retailer, exact, [], minimum_read=1, policy=policy)
    return _verdict(query, retailer, products, unread, minimum_read=minimum_read, policy=policy)


def ground_truth(
    ingredient_name: str,
    n: int = 5,
    *,
    readers: list[RetailerReader],
    cache: ProductCache | None = None,
    minimum_read: int = _MINIMUM_READ,
    policy: ContainsPolicy | None = None,
) -> IngredientVerdict:
    """Read the top `n` products for `ingredient_name` and say how often they carry nuts or peanuts.

    A result any retailer has cached answers first, with no browser request at all. Otherwise readers are tried in
    order; a blocked, empty or thin one hands over to the next. Fewer than `minimum_read` distinct readable products
    give 'insufficient', unless the query names one exact product and that product was read (then its own
    ingredients settle it). Unread pages that could change the answer under `policy` also give 'insufficient'.
    Blocked, empty and partial reads are never cached.
    """
    policy = policy or ContainsPolicy()
    if cache:
        for reader in readers:
            cached = cache.get(reader.name, ingredient_name, n)
            if cached:
                return _judge(ingredient_name, reader.name, cached, [], minimum_read, policy)
    blocked = False
    insufficient: IngredientVerdict | None = None
    for reader in readers:
        try:
            products, unread = _read_products(reader, ingredient_name, n)
        except RetailerBlocked:
            blocked = True
            continue
        if not products and not unread:
            continue
        found = _judge(ingredient_name, reader.name, products, unread, minimum_read, policy)
        if found.status == "resolved":
            if cache and not unread:
                cache.put(reader.name, ingredient_name, n, products)
            return found
        insufficient = insufficient or found
    if insufficient:
        return insufficient
    return IngredientVerdict(ingredient=ingredient_name, status="blocked" if blocked else "not_found")
