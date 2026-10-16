"""Value types shared by the readers, the classifier and the verdict."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductRef(BaseModel):
    retailer: str = Field(description="Which retailer's shop the product is on, e.g. 'ocado'.")
    name: str = Field(description="The product's name as the search results show it.")
    url: str = Field(description="Absolute URL of the product page, without tracking parameters.")


class Product(BaseModel):
    retailer: str = Field(description="Which retailer's shop the product was read from, e.g. 'ocado'.")
    name: str = Field(description="The product's name.")
    url: str = Field(description="Absolute URL of the product page.")
    ingredients_text: str = Field(description="The ingredients list exactly as the page prints it.")
    allergy_text: str = Field(default="", description="The allergy advice exactly as the page prints it; may be empty.")


class AllergenFacts(BaseModel):
    tree_nut_ingredients: list[str] = Field(
        description="Tree nut terms found in the ingredients list, in the order they appear."
    )
    peanut_ingredients: list[str] = Field(description="Peanut terms found in the ingredients list.")
    may_contain_tree_nut: bool = Field(description="A 'may contain' warning names tree nuts. Not an ingredient.")
    may_contain_peanut: bool = Field(description="A 'may contain' warning names peanuts. Not an ingredient.")
    may_contain_quote: str | None = Field(
        default=None, description="The 'may contain' text that names nuts or peanuts, quoted as printed."
    )
