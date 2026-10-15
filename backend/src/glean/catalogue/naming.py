"""The batched LLM call that names items nothing in the catalogue matched (#123)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from glean.llm import Feature

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from glean.llm import LLMRouter

NAMING_SYSTEM_PROMPT = """You name items for a household catalogue (groceries and household goods).
For each raw name (a shopping-list entry, receipt line or typed item), give the one plain canonical name.

Rules:
- Strip brands, pack sizes, quantities and marketing words: "Tesco Fresh Cut Coriander 30g" -> "coriander".
- Keep the form words that make a different ingredient: "tinned chickpeas", "frozen peas", "dried oregano".
- Household goods (toilet roll, birthday candles, shampoo, cat food) keep a name close to what was written.
- Use lower case, singular where natural, no punctuation.
- If a name can't be identified as any food or household item at all (a typo, random letters, nonsense),
  set canonical_name to null. Never guess a food for nonsense.
- Return exactly one entry per input, with the input copied unchanged."""


class NameRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    input: str = Field(description="The raw name to name.")
    group: str = Field(description="The ingredient group the decision model placed it in, as a hint.")


class NamedIngredient(BaseModel):
    input: str = Field(description="The raw name, copied unchanged from the request.")
    canonical_name: str | None = Field(
        description="The plain canonical name, or null when the input can't be identified as any item."
    )


class NamingResponse(BaseModel):
    names: list[NamedIngredient] = Field(description="One entry per requested name.")


def name_items(
    requests: Sequence[NameRequest], *, llm_router: LLMRouter, context: str | None = None, **kwargs: object
) -> Mapping[str, str | None]:
    """Name every request in one call. Returns canonical names by input; names the model skipped are absent."""
    lines = "\n".join(f"- {request.input} (group: {request.group})" for request in requests)
    where = f"These came from: {context}.\n" if context else ""
    response = llm_router.invoke(
        Feature.INGREDIENT_NORMALISATION,
        NamingResponse,
        [SystemMessage(content=NAMING_SYSTEM_PROMPT), HumanMessage(content=f"{where}Name these items:\n{lines}")],
        **kwargs,
    )
    return {entry.input: entry.canonical_name for entry in response.names}
