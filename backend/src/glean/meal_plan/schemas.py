from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from glean.meal_plan.tools import FeedbackChip
from glean.observability import logger
from glean.profile.schemas import ProfileNote, ProteinTarget, SpiceTolerance
from glean.recipes.attributes import DishType, MainCarb, MainProtein

# Twelve weeks of dinners, with room for a household that cooks twice a day.
COOKED_HISTORY_WINDOW_ITEMS = 200
# A thumbs down does not expire, so the app sends the cook that carries one however old it is, on top of the
# window. It sends at most this many of those too-old cooks too, which keeps the request bounded at
# COOKED_HISTORY_WINDOW_ITEMS + DISLIKED_HISTORY_ITEMS rows however many years of dislikes a household has.
DISLIKED_HISTORY_ITEMS = 200
MAX_COOKED_HISTORY_ITEMS = COOKED_HISTORY_WINDOW_ITEMS + DISLIKED_HISTORY_ITEMS
# A rating is a thumb on a cooked meal. The values are the wire vocabulary the app stores in `meal_ratings`.
Rating = Literal["up", "down"]
# Long enough for "too sweet for the kids, and the sauce split", short enough that the history window
# cannot be used as a free-text channel. Counted in Unicode code points, which is what Pydantic's
# `max_length` and the app's note sheet both count -- not grapheme clusters.
MAX_COOKED_NOTE_LENGTH = 500
# The week's note: a line, such as "kids are away Wednesday, something spicy then", not a letter. Short on purpose,
# because it is the one free text a household sends a model on every Generate.
MAX_FEEDBACK_NOTE_LENGTH = 200
# The household profile as a Generate sends it (V13b): tighter than the interview's own ceilings, because it rides
# every Generate and every swap. The app clips to these numbers on the way out (newest notes first), so a request
# past them is a forged or broken client and is refused with a 422 rather than clipped here. Code points, as above.
MAX_PLANNING_LIST_ENTRIES = 20
MAX_PLANNING_TEXT_CHARS = 60
MAX_PLANNING_PARAGRAPH_CHARS = 500
MAX_PLANNING_NOTES = 20
MAX_PLANNING_NOTE_CHARS = 200
# A favourite meal is matched to a corpus recipe by its exact title when the interview found no recipe id, and a third
# of the corpus's titles are longer than 60, so it takes the interview's own 120 (owner ruling 2026-10-27).
MAX_PLANNING_FAVOURITE_CHARS = 120

_PlanningText = Annotated[str, Field(min_length=1, max_length=MAX_PLANNING_TEXT_CHARS)]


class CompressedPantryItem(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    food_group: str | None = Field(
        default=None, description="Food group of the ingredient's category; null when the ingredient is uncategorised"
    )
    urgency_score: float = Field(
        description="Higher score = more urgent to use (expiring soon, long unused, low quantity)"
    )
    expires_in_days: int | None = Field(
        default=None,
        description=(
            "Whole days until the item goes off; null when its expiry date is unknown. Optional so an "
            "older app build that does not send it still works."
        ),
    )


class RecipeHistoryItem(BaseModel):
    recipe_id: int
    title: str
    last_cooked_at: datetime | None = Field(
        description="ISO datetime of last time this recipe was cooked; null if never cooked"
    )
    food_groups: list[str] = Field(description="Food groups this recipe covers (e.g. ['protein', 'veg'])")


class CookedHistoryItem(BaseModel):
    """One meal the household actually cooked, from the last 12 weeks.

    `recipe_id` is the corpus recipe id, which the app keeps as the plan entry's
    `externalIdSnapshot`. It is null for meals cooked before the app stored that
    snapshot, so `title` is the fallback identity.

    `rating` is the household's thumb on this cook, which selects the recipe in and out of planning
    (`meal_plan.eligibility`): the most recent rated cook decides. `note` is the comment they attached
    to it. Notes are accepted and validated here but are deliberately never handed to a model -- see
    `meal_plan.service` for the seam the screened-feedback screen plugs into.
    """

    recipe_id: str | None = Field(
        default=None, description="Corpus recipe id; the same id corpus suggestions carry as external_id"
    )
    title: str
    cooked_at: datetime = Field(description="ISO datetime the meal was cooked, with an offset (the app sends UTC)")
    rating: Rating | None = Field(
        default=None,
        description="The household's thumb on this cook; null when the meal was not rated",
    )
    note: str | None = Field(
        default=None,
        max_length=MAX_COOKED_NOTE_LENGTH,
        description=(
            "The comment attached to the rating; null when there is none. Stored and validated, but not "
            "read by planning until the feedback screen screens notes for prompt injection."
        ),
    )

    @field_validator("cooked_at")
    @classmethod
    def _read_a_missing_offset_as_utc(cls, value: datetime) -> datetime:
        """State the timezone instead of guessing it at the age arithmetic.

        The app sends `toUtc().toIso8601String()`, so this only catches an older build's local wall
        clock: reading it as UTC is explicit here, rather than silently assumed 30 lines away.
        """
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class HumanFeedback(BaseModel):
    """What the household told the planner about this week: chips, and an optional note (spec 6.5).

    Every chip is optional and none is the default. What a chip does to the week lives in
    `meal_plan.tools.FeedbackChip`. The note is screened before any model reads it (`meal_plan.feedback`): a note
    that fails is dropped and the chips still apply.
    """

    chips: list[FeedbackChip] = Field(
        default_factory=list, max_length=len(FeedbackChip), description="The week's chips; a repeat counts once."
    )
    note: str | None = Field(
        default=None,
        max_length=MAX_FEEDBACK_NOTE_LENGTH,
        description="The household's note for this week. Screened for prompt injection; used only if it passes.",
    )

    @field_validator("chips", mode="before")
    @classmethod
    def _ignore_unknown_chips(cls, chips: object) -> object:
        """Drop a chip this backend does not know, so a newer app's chip costs that chip, not the whole Generate."""
        if not isinstance(chips, list):
            return chips
        known = {chip.value for chip in FeedbackChip}
        unknown = [chip for chip in chips if isinstance(chip, str) and chip not in known]
        if unknown:
            logger.warning(
                "ignoring feedback chips this backend does not know",
                extra={"unknown_chips": [chip[:40] for chip in unknown[: len(FeedbackChip)]]},
            )
        return [chip for chip in chips if not (isinstance(chip, str) and chip not in known)]

    @field_validator("chips")
    @classmethod
    def _each_chip_once(cls, chips: list[FeedbackChip]) -> list[FeedbackChip]:
        return list(dict.fromkeys(chips))


class FeedbackNoteOutcome(StrEnum):
    """What happened to the week's note. The app says "Couldn't use that note" for either kind of drop."""

    USED = "used"
    NOT_A_PREFERENCE = "not_a_preference"
    UNAVAILABLE = "unavailable"


class PlanningFavourite(BaseModel):
    """A favourite dinner, and the corpus recipe the interview matched it to, if any."""

    text: str = Field(min_length=1, max_length=MAX_PLANNING_FAVOURITE_CHARS)
    recipe_id: str | None = Field(default=None, max_length=200)


class PlanningNote(ProfileNote):
    """One of the profile's newest notes, shorter than the profile itself allows."""

    text: str = Field(min_length=1, max_length=MAX_PLANNING_NOTE_CHARS)


class PlanningProfile(BaseModel):
    """The household profile (spec 6.4) as planning reads it: the device's own JSON, bounded for the wire.

    Disliked ingredients are a hard exclusion (`meal_plan.household`), the favourites, likes and protein targets are
    scorer terms, and the free text reaches a prompt only once the injection screen passed it. A top-level key this
    backend does not know is ignored, so a newer app's profile costs that key, not the Generate; but a note or a
    protein target is the profile's own strict shape (`profile.schemas`), so an unknown key inside one is a 422.
    """

    version: int = 1
    favourite_meals: list[PlanningFavourite] = Field(default_factory=list, max_length=MAX_PLANNING_LIST_ENTRIES)
    loved_ingredients: list[_PlanningText] = Field(default_factory=list, max_length=MAX_PLANNING_LIST_ENTRIES)
    disliked_ingredients: list[_PlanningText] = Field(default_factory=list, max_length=MAX_PLANNING_LIST_ENTRIES)
    cuisines_liked: list[_PlanningText] = Field(default_factory=list, max_length=MAX_PLANNING_LIST_ENTRIES)
    cuisines_avoided: list[_PlanningText] = Field(default_factory=list, max_length=MAX_PLANNING_LIST_ENTRIES)
    protein_targets: list[ProteinTarget] = Field(default_factory=list, max_length=MAX_PLANNING_LIST_ENTRIES)
    spice_tolerance: SpiceTolerance | None = None
    habits: str = Field(default="", max_length=MAX_PLANNING_PARAGRAPH_CHARS)
    household: str = Field(default="", max_length=MAX_PLANNING_PARAGRAPH_CHARS)
    notes: list[PlanningNote] = Field(
        default_factory=list, max_length=MAX_PLANNING_NOTES, description="The newest notes, newest first."
    )


class MealPlanRequest(BaseModel):
    source: Literal["saved", "corpus"] = Field(
        default="saved",
        description="Choose from the user's saved recipes (recipe_history) or from the server's recipe corpus",
    )
    pantry: list[CompressedPantryItem] = Field(
        description="Top-N urgency-scored pantry items (staples and zero-quantity items excluded)"
    )
    recipe_history: list[RecipeHistoryItem] = Field(
        default_factory=list, description="All saved recipes with their last_cooked_at timestamps"
    )
    cooked_history: list[CookedHistoryItem] = Field(
        default_factory=list,
        max_length=MAX_COOKED_HISTORY_ITEMS,
        description=(
            "Meals cooked in the last 12 weeks (newest-idle first is not required; the plan avoids repeats), "
            "plus the cook carrying a recipe's latest thumbs down even when it is older than the window. "
            "The plan never offers a recipe whose latest rating here is thumbs down."
        ),
    )
    exclude_external_ids: list[str] = Field(
        default_factory=list, description="Corpus recipe IDs already in the plan, never offered again"
    )
    food_group_coverage: dict[str, int] = Field(
        default_factory=dict,
        description="Number of meals cooked this week per food group (e.g. {'protein': 2, 'veg': 1})",
    )
    purchase_tolerance: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = only suggest recipes using pantry ingredients; 1.0 = any recipe regardless of missing items",
    )
    meals_per_week: int = Field(
        ge=1,
        le=7,
        description="Number of meal-plan slots to fill (may be less than full week if plan is partially filled)",
    )
    local_date: date | None = Field(
        default=None,
        description=(
            "The phone's local calendar date, the one `expires_in_days` was measured from. The plan dates "
            "a going-off item by the household's calendar, so it cannot use the server's UTC date. Null "
            "from an app build that does not send it."
        ),
    )
    dietary_flags: list[str] = Field(description="User dietary preferences to respect (e.g. ['vegan', 'gluten-free'])")
    max_active_time_mins: int | None = Field(
        ge=1,
        le=480,
        description="Maximum active cooking time in minutes; null means no limit",
    )
    human_feedback: HumanFeedback | None = Field(
        default=None,
        description="This week's chips and note; null, the default, when the household set nothing.",
    )
    profile: PlanningProfile | None = Field(
        default=None,
        description="The household profile from the device; null when there is none or the interview was skipped.",
    )


class MealPlanRecipe(BaseModel):
    """A recipe selected for the user's current pantry and preferences."""

    model_config = ConfigDict(extra="forbid")

    recipe_id: int = Field(description="Stable saved recipe ID to include in the plan.")
    title: str = Field(description="Human-readable recipe title to show the user.")
    reason: str = Field(description="Human-readable explanation of why this recipe belongs in the meal plan")
    missing_ingredients: list[str] = Field(
        description="Ingredient names not currently in the pantry that would need purchasing"
    )


class MealPlanResponse(BaseModel):
    """Meal-planning recipes returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    suggestions: list[MealPlanRecipe] = Field(description="Ranked recipes that satisfy the request constraints.")


class ReasonKind(StrEnum):
    """What a meal's reason rests on (spec §6.2), so the card can show why it was picked.

    Every proposal meal carries one. `balance` is the default: the pick is about the week's shape,
    variety or fit rather than one piece of evidence.
    """

    URGENT_ITEM = "urgent_item"
    PROFILE = "profile"
    FEEDBACK = "feedback"
    BALANCE = "balance"
    HISTORY = "history"
    ANSWER = "answer"


class NoteEvidence(StrEnum):
    """What a profile note rests on (V15): a rated cook, the answer to the agent's question, or a swap note."""

    RATING = "rating"
    ANSWER = "answer"
    SWAP_NOTE = "swap_note"


class ProfileNote(BaseModel):
    """A short, durable fact the agent inferred about the household, for it to Keep or dismiss (spec §6.4).

    The household's profile never gains one without a Keep. Its bounds are checked by
    `meal_plan.profile_notes`, not the schema, because structured output is not trusted to keep them.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="One short sentence about the household, such as 'You prefer rice over pasta'")
    evidence: NoteEvidence = Field(description="What it rests on: rating, answer or swap_note")


class CorpusMealPlanAlternative(BaseModel):
    """A candidate the model offers instead of the one it chose, for the card's Swap."""

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(description="external_id of the candidate offered as the alternative, copied exactly.")
    title: str = Field(description="Title of that candidate, copied exactly.")
    reason: str = Field(description="One sentence on why this recipe would work instead")
    reason_kind: ReasonKind = Field(
        default=ReasonKind.BALANCE, description="What this alternative's reason rests on (spec §6.2)"
    )


class CorpusMealPlanRecipe(BaseModel):
    """A corpus recipe the model selected from the candidates it was offered."""

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(description="external_id of the chosen candidate, copied exactly.")
    title: str = Field(description="Title of the chosen candidate, copied exactly.")
    reason: str = Field(description="Human-readable explanation of why this recipe belongs in the meal plan")
    reason_kind: ReasonKind = Field(
        default=ReasonKind.BALANCE,
        description="What this meal's reason rests on: urgent_item, profile, feedback, balance, history or answer",
    )
    alternative: CorpusMealPlanAlternative | None = Field(
        default=None,
        description=(
            "One candidate the household could cook instead, chosen from the candidates you were offered and "
            "not among the meals you chose. Null only when nothing suitable is left."
        ),
    )


class CorpusPlannedAlternative(BaseModel):
    """An alternative the model offers for a meal already in the week, so it can be swapped too."""

    model_config = ConfigDict(extra="forbid")

    planned_external_id: str = Field(
        description="external_id of the meal already in the week, copied exactly from planned_meals"
    )
    alternative: CorpusMealPlanAlternative = Field(description="One candidate the household could swap it to")


class CorpusMealPlanResponse(BaseModel):
    """Corpus meal-planning recipes returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    week_summary: str = Field(
        default="", description="One line summing up the week, shown above the meals; empty when the model has none"
    )
    chosen_week: int | None = Field(
        default=None,
        description=(
            "Index into candidate_weeks of the week these meals come from: 0 or 1. Null from a model that did not "
            "say, which the server reads from the meals themselves."
        ),
    )
    suggestions: list[CorpusMealPlanRecipe] = Field(description="Ranked candidates that satisfy the constraints.")
    planned_alternatives: list[CorpusPlannedAlternative] = Field(
        default_factory=list,
        description=(
            "For each meal already in the week, one candidate it could be swapped to. Empty when none are planned."
        ),
    )


class UsedUpPantryItem(BaseModel):
    """One urgent pantry item a planned meal uses up, so the app need not read it out of the reason."""

    name: str
    expires_in_days: int | None = Field(
        default=None, description="Whole days until the item goes off; null when unknown"
    )
    goes_off: str | None = Field(
        default=None,
        description="Weekday the item goes off in the household's calendar (e.g. 'Thu'); null when unknown",
    )


class MealPlanAttributes(BaseModel):
    """The recipe attributes a proposal card labels, from the corpus's enrichment answers (V5, spec 6.5).

    Only known values ride the wire: an attribute the decision model was not confident enough about is null,
    and the card shows no chip for it rather than inventing one. Protein, carb, dish type and a time are the
    labels the V3 design places; cuisine and whole food are measured too but nothing displays them yet, so
    they are not here.
    """

    main_protein: MainProtein | None = Field(default=None, description="G1 main protein; null when unsure.")
    main_carb: MainCarb | None = Field(default=None, description="G1 main carb; null when unsure.")
    dish_type: DishType | None = Field(default=None, description="G1 dish type; null when unsure.")
    active_time_mins: int | None = Field(
        default=None,
        description=(
            "Hands-on minutes to show: the enriched active-time bucket's upper bound, or the recipe's total "
            "time when no bucket is known. Null when neither is."
        ),
    )


class MealPlanAlternative(BaseModel):
    """One swap target: a suggestion that carries no alternative of its own."""

    recipe_id: int | None = None
    external_id: str | None = None
    title: str
    reason: str
    missing_ingredients: list[str] = Field(default_factory=list)
    uses_up: list[UsedUpPantryItem] = Field(default_factory=list)
    # Always set on a corpus proposal; saved mode, which the retiring sync route still serves, leaves it at balance.
    reason_kind: ReasonKind = ReasonKind.BALANCE
    attributes: MealPlanAttributes = Field(
        default_factory=MealPlanAttributes,
        description="The swap target's labels, so the panel can show what it is.",
    )


class MealPlanSuggestion(BaseModel):
    """One proposed meal: a saved recipe (recipe_id) or a corpus recipe (external_id)."""

    recipe_id: int | None = None
    external_id: str | None = None
    title: str
    reason: str
    # Filled only by saved-mode plans; the app derives shopping gaps from the recipe itself.
    missing_ingredients: list[str] = Field(default_factory=list)
    # Urgent pantry items this meal uses, soonest to go off first. A proposal field the app shows later.
    uses_up: list[UsedUpPantryItem] = Field(default_factory=list)
    # Always set on a corpus proposal; saved mode, which the retiring sync route still serves, leaves it at balance.
    reason_kind: ReasonKind = ReasonKind.BALANCE
    # The meal to cook instead if the household swaps this one; null when nothing suitable is left.
    alternative: MealPlanAlternative | None = None
    attributes: MealPlanAttributes = Field(
        default_factory=MealPlanAttributes,
        description="The card's labels, from the corpus's enrichment answers; empty when nothing is known.",
    )


class PlannedMealAlternative(BaseModel):
    """An alternative for a meal already in the week, so it can be swapped without regenerating."""

    external_id: str = Field(description="Corpus id of the meal already in the week")
    alternative: MealPlanSuggestion = Field(
        description="The swap target. It is a suggestion, so its own `alternative` is always null."
    )


class MealPlanResult(BaseModel):
    """The proposal: what POST /meal-plan and a finished session return. New fields are additive."""

    suggestions: list[MealPlanSuggestion]
    week_summary: str = Field(
        default="",
        description=(
            "One line shown above the meals. Always set on a corpus proposal, template text when the plan is "
            "degraded; empty only for a saved-mode plan, which the retiring sync route still serves."
        ),
    )
    planned_alternatives: list[PlannedMealAlternative] = Field(
        default_factory=list,
        description="An alternative per planned meal that came from the corpus; empty when none are planned.",
    )
    degraded: bool = Field(
        default=False,
        description=(
            "True when finalise fell back to the scorer's picks with template text. It looks like any other "
            "proposal; degradation is recorded in logs and evals, not shown to the household."
        ),
    )
    feedback_note: FeedbackNoteOutcome | None = Field(
        default=None,
        description=(
            "What became of the week's note: used, or dropped and why. Null when no note was sent. The app shows "
            '"Couldn\'t use that note" for a drop; the chips apply either way.'
        ),
    )
    profile_notes: list[ProfileNote] = Field(
        default_factory=list,
        description=(
            "What the agent noticed about the household, for the 'Glean noted' card: at most three, each with "
            "evidence from this session. Empty on a degraded plan; a swap carries the proposal's notes unchanged."
        ),
    )
