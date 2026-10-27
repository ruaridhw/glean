"""The household profile and the taste interview's wire contract (spec §6.4).

The profile is versioned JSON so its shape can grow without a database migration on the device;
this module is the authority for that shape, and the app stores what it gets here.
"""

from __future__ import annotations

import datetime as dt  # noqa: TC003 - Pydantic resolves these field types at runtime.
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Seven questions in one interview: the five fixed openers and at most two follow-ups.
MAX_TURNS = 7

# Nothing a client sends is trusted to be small: every list and string has a ceiling, generous enough
# that the app never meets it, so a forged or runaway request is a 422 rather than a 3 MB prompt.
MAX_LIST_ENTRIES = 25
MAX_TEXT_CHARS = 120
MAX_PARAGRAPH_CHARS = 500
MAX_QUESTION_CHARS = 300
MAX_ID_CHARS = 64
MAX_OPTIONS = 10
MAX_NOTES = 50
MAX_PROTEIN_TARGETS = 12  # one per MainProtein value

_Text = Annotated[str, Field(min_length=1, max_length=MAX_TEXT_CHARS)]
_Paragraph = Annotated[str, Field(max_length=MAX_PARAGRAPH_CHARS)]


class SpiceTolerance(StrEnum):
    """How much heat the household wants. `null` means the interview didn't settle it."""

    NONE = "none"
    MILD = "mild"
    MEDIUM = "medium"
    HOT = "hot"


class MainProtein(StrEnum):
    """The protein a meal is built around (spec §6.1, "Attribute values")."""

    CHICKEN = "chicken"
    TURKEY_OR_DUCK = "turkey_or_duck"
    BEEF = "beef"
    PORK = "pork"
    LAMB = "lamb"
    FISH = "fish"
    SEAFOOD = "seafood"
    BEANS_AND_PULSES = "beans_and_pulses"
    TOFU_OR_PLANT_PROTEIN = "tofu_or_plant_protein"
    VEGETARIAN_OTHER = "vegetarian_other"
    MIXED = "mixed"
    NONE = "none"


class ProfileField(StrEnum):
    """The profile fields a question can target."""

    FAVOURITE_MEALS = "favourite_meals"
    LOVED_INGREDIENTS = "loved_ingredients"
    DISLIKED_INGREDIENTS = "disliked_ingredients"
    CUISINES_LIKED = "cuisines_liked"
    CUISINES_AVOIDED = "cuisines_avoided"
    PROTEIN_TARGETS = "protein_targets"
    SPICE_TOLERANCE = "spice_tolerance"
    HABITS = "habits"
    HOUSEHOLD = "household"
    NOTES = "notes"


class WritableProfileField(StrEnum):
    """The profile fields an interview answer can fill.

    `notes` is not one: feedback writes them (spec §6.4, V15) and the retake is parked, so a follow-up
    aimed there would spend one of the two follow-ups on an answer nobody stores. This is a separate enum
    from `ProfileField` on purpose — the model is sent a JSON schema, and a schema is what stops it naming a
    field nothing writes; a validator would only fail after the model had already chosen.
    """

    FAVOURITE_MEALS = "favourite_meals"
    LOVED_INGREDIENTS = "loved_ingredients"
    DISLIKED_INGREDIENTS = "disliked_ingredients"
    CUISINES_LIKED = "cuisines_liked"
    CUISINES_AVOIDED = "cuisines_avoided"
    PROTEIN_TARGETS = "protein_targets"
    SPICE_TOLERANCE = "spice_tolerance"
    HABITS = "habits"
    HOUSEHOLD = "household"


# Compared by value, because a transcript carries plain JSON strings.
WRITABLE_PROFILE_FIELDS = frozenset(field.value for field in WritableProfileField)


class NoteSource(StrEnum):
    """Where a profile note came from."""

    INTERVIEW = "interview"
    FEEDBACK = "feedback"


class FavouriteMeal(BaseModel):
    """A dinner the household would happily eat every fortnight, and the corpus recipe it is, if any."""

    model_config = ConfigDict(extra="forbid")

    text: _Text = Field(description="The meal as the household said it.")
    recipe_id: str | None = Field(
        default=None,
        max_length=200,
        description="The corpus recipe this meal is, when the title matched one confidently; otherwise null.",
    )


class ProteinTarget(BaseModel):
    """A weekly target for how often a protein should appear on the plan."""

    model_config = ConfigDict(extra="forbid")

    protein: MainProtein = Field(description="The protein the target is about.")
    min_per_week: int | None = Field(default=None, ge=0, le=21, description="Fewest dinners a week with it, or null.")
    max_per_week: int | None = Field(default=None, ge=0, le=21, description="Most dinners a week with it, or null.")

    @model_validator(mode="after")
    def _bounds_are_ordered(self) -> ProteinTarget:
        low, high = self.min_per_week, self.max_per_week
        if low is not None and high is not None and low > high:
            raise ValueError(f"min_per_week {low} is above max_per_week {high}")
        return self


class ProfileNote(BaseModel):
    """One dated fact about the household, kept as the profile's running memory."""

    model_config = ConfigDict(extra="forbid")

    date: dt.date = Field(description="The day the note was recorded.")
    text: Annotated[str, Field(min_length=1, max_length=MAX_PARAGRAPH_CHARS)] = Field(
        description="The note itself, in plain language."
    )
    source: NoteSource = Field(description="Where the note came from.")


class HouseholdProfile(BaseModel):
    """Everything the interview learned about the household, as versioned JSON."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = Field(default=1, description="The profile shape's version. Always 1 today.")
    favourite_meals: list[FavouriteMeal] = Field(
        default_factory=list,
        max_length=MAX_LIST_ENTRIES,
        description="Dinners they would happily eat every fortnight.",
    )
    loved_ingredients: list[_Text] = Field(
        default_factory=list, max_length=MAX_LIST_ENTRIES, description="Ingredients they love."
    )
    disliked_ingredients: list[_Text] = Field(
        default_factory=list, max_length=MAX_LIST_ENTRIES, description="Ingredients to never plan."
    )
    cuisines_liked: list[_Text] = Field(
        default_factory=list, max_length=MAX_LIST_ENTRIES, description="Cuisines they love."
    )
    cuisines_avoided: list[_Text] = Field(
        default_factory=list, max_length=MAX_LIST_ENTRIES, description="Cuisines to never plan."
    )
    protein_targets: list[ProteinTarget] = Field(
        default_factory=list,
        max_length=MAX_PROTEIN_TARGETS,
        description="How often each protein should appear in a week.",
    )
    spice_tolerance: SpiceTolerance | None = Field(default=None, description="How much heat they want, or null.")
    habits: _Paragraph = Field(default="", description="How they plan and cook now, in their own words.")
    household: _Paragraph = Field(default="", description="Who eats at the table, in their own words.")
    notes: list[ProfileNote] = Field(
        default_factory=list, max_length=MAX_NOTES, description="The running memory of dated notes."
    )
    dismissed_notes: list[_Text] = Field(
        default_factory=list,
        max_length=MAX_NOTES,
        description=(
            "Notes the planner offered that the household dismissed, newest last, so the planner does not offer "
            "them again. Absent from a profile written before they were kept, which reads as none."
        ),
    )
    interviewed_at: dt.datetime | None = Field(default=None, description="When the interview finished, or null.")


class InterviewQuestion(BaseModel):
    """One question in the interview, and the profile field its answer fills."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(min_length=1, max_length=MAX_ID_CHARS)] = Field(
        description="Stable identifier for this question in this interview."
    )
    text: Annotated[str, Field(min_length=1, max_length=MAX_QUESTION_CHARS)] = Field(
        description="The question to show the user."
    )
    options: list[_Text] = Field(
        default_factory=list, max_length=MAX_OPTIONS, description="Tappable answers; may be empty."
    )
    field: ProfileField = Field(description="The profile field this question fills.")
    skippable: Literal[True] = Field(default=True, description="Always true: every turn can be skipped.")


# The five fixed openers, in the order the interview asks them (spec §6.4). They live with the
# contract because the app renders them and the request validator checks them: a stateless endpoint
# can't trust a transcript's own account of what was asked.
OPENERS: tuple[InterviewQuestion, ...] = (
    InterviewQuestion(
        id="opener-favourite-meals",
        text="What are three dinners you'd happily eat every fortnight?",
        field=ProfileField.FAVOURITE_MEALS,
    ),
    InterviewQuestion(
        id="opener-never-want",
        text="Anything you never want to see on the plan?",
        field=ProfileField.DISLIKED_INGREDIENTS,
    ),
    InterviewQuestion(
        id="opener-love",
        text="Any cuisines or ingredients you love?",
        field=ProfileField.LOVED_INGREDIENTS,
    ),
    InterviewQuestion(
        id="opener-weeks",
        text="How do your weeks usually go?",
        options=[
            "Quick weeknights",
            "Batch cook at the weekend",
            "Leftovers",
            "One treat meal",
            "Guests often",
        ],
        field=ProfileField.HABITS,
    ),
    InterviewQuestion(
        id="opener-table",
        text="Who's usually at the table?",
        field=ProfileField.HOUSEHOLD,
    ),
)


def question_for_turn(turn: int) -> InterviewQuestion:
    """The server's own question for a 1-based turn number."""
    return OPENERS[turn - 1]


def expected_question_id(index: int) -> str:
    """The id the transcript's `index`-th answered turn must carry, counting from 0."""
    return OPENERS[index].id if index < len(OPENERS) else f"follow-up-{index + 1}"


class InterviewAnswer(BaseModel):
    """What the user did with one question: typed something, tapped options, skipped, or nothing."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=2_000, description="What they typed, if anything.")
    options: list[_Text] = Field(
        default_factory=list, max_length=MAX_OPTIONS, description="Which offered options they chose."
    )
    skipped: bool = Field(default=False, description="True when they skipped this turn.")


class TranscriptTurn(BaseModel):
    """One answered question: what was asked, and what came back."""

    model_config = ConfigDict(extra="forbid")

    question: InterviewQuestion = Field(description="The question that was asked.")
    answer: InterviewAnswer = Field(description="What the user answered.")


class InterviewRequest(BaseModel):
    """The interview so far. Stateless: the app sends the whole transcript on every turn."""

    model_config = ConfigDict(extra="forbid")

    transcript: list[TranscriptTurn] = Field(
        default_factory=list, max_length=MAX_TURNS, description="Every answered turn, oldest first."
    )
    draft_profile: HouseholdProfile = Field(
        default_factory=HouseholdProfile, description="The profile the app holds, which the turn refines."
    )

    @model_validator(mode="after")
    def _answers_belong_to_this_interview(self) -> InterviewRequest:
        """The transcript must be the questions this interview asks, in order.

        A client that sends its own question ids could otherwise skip the openers entirely, or file an
        answer against a field nothing writes. The opener's field is the server's, not the client's.
        """
        for index, turn in enumerate(self.transcript):
            expected = expected_question_id(index)
            if turn.question.id != expected:
                raise ValueError(f"turn {index + 1} answers {turn.question.id!r}, but this interview asks {expected!r}")
            opener = OPENERS[index] if index < len(OPENERS) else None
            if opener is not None and turn.question.field is not opener.field:
                raise ValueError(
                    f"turn {index + 1} answers {expected!r} for {turn.question.field.value}, "
                    f"but {expected!r} fills {opener.field.value}"
                )
            if opener is None and turn.question.field.value not in WRITABLE_PROFILE_FIELDS:
                raise ValueError(
                    f"turn {index + 1} targets {turn.question.field.value}, which the interview never writes"
                )
        return self


class InterviewQuestionResponse(BaseModel):
    """There is another question to ask."""

    status: Literal["question"] = "question"
    question: InterviewQuestion = Field(description="The next question.")
    turn: int = Field(ge=1, le=MAX_TURNS, description="Which question this is, counting from 1.")
    max_turns: int = Field(default=MAX_TURNS, description="The most questions one interview asks.")
    dropped_answer: bool = Field(default=False, description="True when the last answer failed screening.")


class InterviewDoneResponse(BaseModel):
    """The interview is finished."""

    status: Literal["done"] = "done"
    profile: HouseholdProfile = Field(description="The finished profile.")
    summary: str = Field(description="Two short lines for the user to confirm.")
    dropped_answer: bool = Field(default=False, description="True when the last answer failed screening.")


InterviewResponse = Annotated[InterviewQuestionResponse | InterviewDoneResponse, Field(discriminator="status")]


class ProfileDraft(BaseModel):
    """The profile as the model extracted it, before the server matches recipes and stamps the version."""

    model_config = ConfigDict(extra="forbid")

    favourite_meals: list[str] = Field(description="Dinners they would happily eat every fortnight, one per entry.")
    loved_ingredients: list[str] = Field(description="Ingredients they love.")
    disliked_ingredients: list[str] = Field(description="Ingredients they never want planned.")
    cuisines_liked: list[str] = Field(description="Cuisines they love.")
    cuisines_avoided: list[str] = Field(description="Cuisines they never want planned.")
    protein_targets: list[ProteinTarget] = Field(description="How often each protein should appear in a week.")
    spice_tolerance: SpiceTolerance | None = Field(description="How much heat they want, or null if unanswered.")
    habits: str = Field(description="How they plan and cook now, in their words.")
    household: str = Field(description="Who eats at the table, in their words.")


class FollowUp(BaseModel):
    """A follow-up question the model chose, or nothing when it has enough to finish."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, description="One question, in the same voice as the openers.")
    field: WritableProfileField = Field(description="The profile field the answer will fill.")
    options: list[str] = Field(default_factory=list, description="Two to five short tappable answers, or empty.")


class InterviewTurn(BaseModel):
    """One model turn: the profile so far, plus either a follow-up question or a finished summary."""

    model_config = ConfigDict(extra="forbid")

    draft_profile: ProfileDraft = Field(description="The whole profile, with every answer so far folded in.")
    question: FollowUp | None = Field(description="The next follow-up, or null to finish the interview now.")
    summary: str = Field(description="Two short lines for the user to confirm; empty until the interview finishes.")
