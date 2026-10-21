#!/usr/bin/env python3
"""Migrate the recipe corpus and its dietary decisions into DynamoDB (F1/#162). Owner-run.

Reads every recipe blob and the dietary JSONL from a corpus source, writes each recipe with its SOURCE
pointer in one transaction, writes the dietary decisions as ANSWER items, then builds the S3 projection
planning reads. Idempotent: a second run compares before writing and stores nothing.

The table is provisioned at 5 WCU, so the run paces itself. A recipe write is a transaction of two items,
which DynamoDB charges at twice the item size's write units (a 4 KB body is 8 WCU, the pointer 2), and each
answer is a 1 WCU write; on a 632-recipe corpus that is roughly 10,000 WCU, about 42 minutes at 4 WCU/s.
Throttles are retried with backoff, and `--wcu-per-second` trades time for headroom.

    # rehearse against a local corpus, writing nothing
    uv run python scripts/migrate_recipe_corpus.py --table glean-recipes-dev \\
        --local .cache/glean_recipe_cache --dry-run

    # the real run, from the dev/prod recipe-cache bucket, into the dev table
    uv run python scripts/migrate_recipe_corpus.py --table glean-recipes-dev \\
        --bucket glean-recipe-cache-dev-040396448697

The script refuses any table whose name contains "prod" unless `--i-am-the-owner` is passed, and never
prints a recipe's content.
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.corpus_store import open_corpus, projection_store_for

from glean.meal_plan.dietary_decisions import DietaryDecisionStore, dietary_answers
from glean.recipes.corpus import RecipeCorpusStore, recipe_payload
from glean.recipes.dynamo_corpus import DynamoCorpusBackend
from glean.recipes.projection import ProjectionStore, RecipeProjection, build_projection

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.recipes.answers import RecipeAnswer
    from glean.recipes.stored import StoredRecipe

CHECKPOINT_EVERY = 25
DEFAULT_WCU_PER_SECOND = 4.0  # under the table's 5 WCU, leaving room for the API's own reads and writes


class OwnerApprovalError(Exception):
    """A prod table was named without the owner saying so."""


@dataclass(frozen=True)
class MigrationPlan:
    """What the migration will write: every recipe, its answers, and the write units that costs."""

    recipes: list[StoredRecipe]
    answers: dict[str, list[RecipeAnswer]]

    @property
    def wcu(self) -> int:
        return sum(recipe_wcu(recipe) + len(self.answers.get(recipe.external_id, ())) for recipe in self.recipes)

    def answers_for(self, recipe_id: str) -> list[RecipeAnswer]:
        return self.answers.get(recipe_id, [])

    def duration_seconds(self, wcu_per_second: float) -> float:
        return self.wcu / wcu_per_second if wcu_per_second > 0 else 0.0


@dataclass
class MigrationSummary:
    recipes: int
    recipes_written: int = 0
    answers_written: int = 0
    resumed: int = 0
    projection_recipes: int = 0
    projection_written: bool = False
    projection_skipped: bool = False
    missing: list[str] = field(default_factory=list)
    estimated_seconds: float = 0.0

    def render(self) -> str:
        lines = [
            f"Recipes in the corpus: {self.recipes}",
            f"Written this run: {self.recipes_written} recipes, {self.answers_written} answers"
            + (f" ({self.resumed} already migrated on an earlier run)" if self.resumed else ""),
            f"Estimated cost: {self.estimated_seconds / 60:.0f} min of the table's write capacity",
        ]
        if self.projection_skipped:
            lines.append("Projection: not rebuilt, the corpus is not fully migrated yet")
        else:
            lines.append(f"Projection: {self.projection_recipes} recipes, written={self.projection_written}")
        if self.missing:
            lines.append(
                f"MISSING from the table: {len(self.missing)} recipes ({', '.join(self.missing[:5])}...). "
                "Re-run with --reset-checkpoint."
            )
        return "\n".join(lines)


class Pacer:
    """Spend write capacity at a fixed rate, sleeping whenever the run gets ahead of it."""

    def __init__(
        self,
        wcu_per_second: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._rate = wcu_per_second
        self._clock = clock
        self._sleep = sleep
        self._started = clock()
        self._spent = 0.0

    def spend(self, wcu: float) -> None:
        if self._rate <= 0:
            return
        self._spent += wcu
        ahead = self._spent / self._rate - (self._clock() - self._started)
        if ahead > 0:
            self._sleep(ahead)


class Checkpoint:
    """Which recipes an interrupted run already migrated, so a re-run resumes instead of redoing them."""

    def __init__(self, path: Path | None, *, owner: str) -> None:
        self._path = path
        self._owner = owner
        self.migrated: set[str] = self._load()
        self._unsaved = 0

    def _load(self) -> set[str]:
        if self._path is None or not self._path.exists():
            return set()
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if document.get("owner") != self._owner:
            return set()  # a checkpoint from another table or corpus says nothing about this one
        return set(document.get("migrated", []))

    def add(self, recipe_id: str) -> None:
        self.migrated.add(recipe_id)
        self._unsaved += 1
        if self._unsaved >= CHECKPOINT_EVERY:
            self.save()

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"owner": self._owner, "migrated": sorted(self.migrated)}, indent=0),
            encoding="utf-8",
        )
        self._unsaved = 0


def recipe_wcu(recipe: StoredRecipe) -> int:
    """Write units for one recipe's transaction: the body item plus the SOURCE pointer, billed twice."""
    body_bytes = len(json.dumps(recipe_payload(recipe), sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return 2 * max(1, math.ceil(body_bytes / 1024)) + 2


def main(
    argv: Sequence[str] | None = None,
    *,
    backend: DynamoCorpusBackend | None = None,
    corpus_source: RecipeCorpusStore | None = None,
    projection_store: ProjectionStore | None = None,
) -> int:
    args = _parse_args(argv)
    try:
        _refuse_prod(args.table, i_am_the_owner=args.i_am_the_owner)
    except OwnerApprovalError as error:
        print(f"Refusing to run: {error}")
        return 2

    source = corpus_source if corpus_source is not None else _open_source(args)
    projections = projection_store if projection_store is not None else _open_projection(args)
    plan = _plan(source)
    print(
        f"Migration plan: {len(plan.recipes)} recipes, "
        f"{sum(len(answers) for answers in plan.answers.values())} answers, "
        f"{plan.wcu} write units, about {plan.duration_seconds(args.wcu_per_second) / 60:.0f} min "
        f"at {args.wcu_per_second:g} WCU/s"
    )
    if args.dry_run:
        print("Dry run: wrote nothing.")
        return 0

    target = (
        backend if backend is not None else DynamoCorpusBackend(args.table, projection=projections, region=args.region)
    )
    summary = migrate(plan, target, checkpoint=_checkpoint(args), wcu_per_second=args.wcu_per_second, limit=args.limit)
    projection = _write_projection(plan, summary, target)
    summary.projection_recipes = len(projection.recipes) if projection is not None else 0
    summary.projection_skipped = projection is None
    print(summary.render())
    return 1 if summary.missing else 0


def migrate(
    plan: MigrationPlan,
    backend: DynamoCorpusBackend,
    *,
    checkpoint: Checkpoint,
    wcu_per_second: float = DEFAULT_WCU_PER_SECOND,
    limit: int | None = None,
) -> MigrationSummary:
    """Write every planned recipe and its answers, paced, resuming from the checkpoint."""
    pacer = Pacer(wcu_per_second)
    summary = MigrationSummary(recipes=len(plan.recipes), estimated_seconds=plan.duration_seconds(wcu_per_second))
    resumed: list[str] = []
    for recipe in plan.recipes[: limit if limit is not None else len(plan.recipes)]:
        if recipe.external_id in checkpoint.migrated:
            summary.resumed += 1
            resumed.append(recipe.external_id)
            continue
        pacer.spend(recipe_wcu(recipe))
        summary.recipes_written += bool(backend.upsert(recipe))
        answers = plan.answers_for(recipe.external_id)
        if answers:
            summary.answers_written += backend.save_answers(answers, rebuild_projection=False)
        checkpoint.add(recipe.external_id)
    checkpoint.save()
    # A checkpoint from an older run can name recipes a wiped table no longer has: say so rather than skip.
    summary.missing = [recipe_id for recipe_id in resumed if backend.get(recipe_id) is None]
    return summary


def _write_projection(
    plan: MigrationPlan, summary: MigrationSummary, backend: DynamoCorpusBackend
) -> RecipeProjection | None:
    """Build the projection from the source corpus, once the whole corpus is in the table.

    Built from what was just migrated rather than scanned back out of the table: at 5 RCU a consistent
    scan of 632 bodies is minutes of throttling for data the run already holds.
    """
    if summary.missing or summary.resumed + summary.recipes_written < summary.recipes:
        return None
    answers = [answer for answers in plan.answers.values() for answer in answers]
    projection = build_projection(plan.recipes, answers)
    summary.projection_written = backend.write_projection(projection)
    return projection


def _plan(source: RecipeCorpusStore) -> MigrationPlan:
    recipes = sorted(source.all_recipes(), key=lambda recipe: recipe.external_id)
    known = {recipe.external_id for recipe in recipes}
    answers: dict[str, list[RecipeAnswer]] = {}
    for answer in dietary_answers(DietaryDecisionStore(source.store).load()):
        if answer.recipe_id in known:
            answers.setdefault(answer.recipe_id, []).append(answer)
    return MigrationPlan(recipes=recipes, answers=answers)


def _refuse_prod(table: str, *, i_am_the_owner: bool) -> None:
    if "prod" in table.casefold() and not i_am_the_owner:
        raise OwnerApprovalError(
            f"{table!r} looks like a prod table; pass --i-am-the-owner once you have the owner's approval"
        )


def _checkpoint(args: argparse.Namespace) -> Checkpoint:
    owner = f"{args.table}|{args.bucket or args.local}"
    default = Path(tempfile.gettempdir()) / f"migrate-recipe-corpus-{args.table}.json"
    path = None if args.no_checkpoint else (args.checkpoint or default)
    if args.reset_checkpoint and path is not None:
        path.unlink(missing_ok=True)
    return Checkpoint(path, owner=owner)


def _open_source(args: argparse.Namespace) -> RecipeCorpusStore:
    return open_corpus(bucket=args.bucket, cache_dir=args.local, region=args.region)


def _open_projection(args: argparse.Namespace) -> ProjectionStore:
    return projection_store_for(bucket=args.bucket, cache_dir=args.local, region=args.region)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate the recipe corpus into DynamoDB (F1/#162).")
    parser.add_argument("--table", required=True, help="DynamoDB recipes table, e.g. glean-recipes-dev.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--bucket", help="S3 recipe-cache bucket holding the corpus/ prefix; also takes the projection."
    )
    source.add_argument("--local", type=Path, help="Local cache root holding corpus/; also takes the projection.")
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan and the estimate, write nothing.")
    parser.add_argument("--limit", type=int, default=None, help="Migrate only the first N recipes (a smoke run).")
    parser.add_argument("--wcu-per-second", type=float, default=DEFAULT_WCU_PER_SECOND)
    parser.add_argument("--checkpoint", type=Path, default=None, help="Resume file (default in /tmp).")
    parser.add_argument("--no-checkpoint", action="store_true")
    parser.add_argument("--reset-checkpoint", action="store_true")
    parser.add_argument(
        "--i-am-the-owner",
        action="store_true",
        help="Required to write a table whose name contains prod. Prod writes need the owner's approval.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
