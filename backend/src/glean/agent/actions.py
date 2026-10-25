"""What the `plan` node may decide: one typed `NextAction`, read through structured output (ADR 0012).

The model never calls a provider tool. It answers a `PlanStep` whose `action` is a discriminated union, so
the choice of tool, its arguments and the final proposal are all validated data before anything runs (spec
§7: "The agent picks actions through a typed NextAction union, not provider tool-calling"). Every argument is
typed: a filter's fields and operators are the tools' own allowlist enums, so a field outside it is a
validation error, never a query.

**Extension point (V11).** `ask_household` -- a question and its options -- joins the union as a third
member, `AskHousehold(kind="ask_household", question=..., options=[...])`. The graph routes it to `act`, which
calls LangGraph's `interrupt()` and parks the run as `waiting_for_user` until `resume(session_id, message)`
arrives. It is deliberately not here yet: no route resumes a session, and an action the graph cannot carry
out must not be one the model can choose.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from glean.meal_plan import tools
from glean.meal_plan.schemas import CorpusMealPlanResponse
from glean.meal_plan.tools import MAX_FILTER_LIMIT, PredicateField, PredicateOp


class PredicateArgs(BaseModel):
    """One filter predicate (spec §6.2): a field and an operator from the allowlist, and its values."""

    model_config = ConfigDict(extra="forbid")

    field: PredicateField
    op: PredicateOp = Field(description="in / not_in for every field; lte / gte compare active_time minutes only")
    values: list[str] = Field(description="The values to compare; one number of minutes for lte / gte")

    def predicate(self) -> tools.Predicate:
        """The tools' predicate. Raises ValueError for an operator its field does not take."""
        return tools.Predicate(self.field, self.op, tuple(self.values))


class RecipeFilterArgs(BaseModel):
    """The filter's shape (spec §6.2). Every clause narrows; nothing here can widen what the session allows."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(
        default=None, description="Words to search titles, cuisines and ingredients for, such as 'korean'"
    )
    include: list[PredicateArgs] = Field(default_factory=list, description="All of these must hold")
    exclude: list[PredicateArgs] = Field(default_factory=list, description="None of these may hold")
    max_active_mins: int | None = Field(
        default=None, description="A tighter hands-on time limit; it may never exceed the household's own cap"
    )
    uses_pantry: list[str] | None = Field(default=None, description="Pantry items every recipe must use")
    exclude_ids: list[str] = Field(default_factory=list, description="external_ids to leave out")
    limit: int = Field(default=MAX_FILTER_LIMIT, description=f"At most {MAX_FILTER_LIMIT}")

    def recipe_filter(self) -> tools.RecipeFilter:
        """The tools' filter. Raises ValueError for a predicate whose operator its field does not take."""
        return tools.RecipeFilter(
            text=self.text,
            include=tuple(predicate.predicate() for predicate in self.include),
            exclude=tuple(predicate.predicate() for predicate in self.exclude),
            max_active_mins=self.max_active_mins,
            uses_pantry=None if self.uses_pantry is None else tuple(self.uses_pantry),
            exclude_ids=tuple(self.exclude_ids),
            limit=self.limit,
        )


class GetEligibleRecipes(BaseModel):
    """Find recipes this household may cook, narrowed by a filter."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["get_eligible_recipes"]
    filter: RecipeFilterArgs = Field(default_factory=RecipeFilterArgs)


class GetRecipes(BaseModel):
    """Read recipes more closely: a summary, or the full ingredient lines and method."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["get_recipes"]
    ids: list[str] = Field(description="external_ids to describe")
    detail: Literal["summary", "full"] = "summary"


class ScoreMealPlan(BaseModel):
    """Score a week of recipes with the scorer's breakdown, to test a substitution."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["score_meal_plan"]
    recipe_ids: list[str] = Field(description="external_ids of the week to score, each once")


class CreateCandidateMealPlans(BaseModel):
    """Ask the scorer for two balanced weeks built from a set of recipes."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["create_candidate_meal_plans"]
    recipe_ids: list[str] = Field(
        default_factory=list, description="external_ids to build from; empty means every recipe you may plan"
    )


type ToolCall = Annotated[
    GetEligibleRecipes | GetRecipes | ScoreMealPlan | CreateCandidateMealPlans, Field(discriminator="name")
]
TOOL_CALL: TypeAdapter[ToolCall] = TypeAdapter(ToolCall)


class CallTool(BaseModel):
    """Run one tool and see its result before deciding again."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["call_tool"]
    call: ToolCall


class Propose(BaseModel):
    """The final answer: the week, a reason per meal, an alternative per meal, and the summary line."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["propose"]
    proposal: CorpusMealPlanResponse


type NextAction = Annotated[CallTool | Propose, Field(discriminator="kind")]


class PlanStep(BaseModel):
    """The `plan` node's structured output. An object at the root, because a schema must be one."""

    model_config = ConfigDict(extra="forbid")

    action: NextAction
