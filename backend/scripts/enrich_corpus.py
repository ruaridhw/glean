#!/usr/bin/env python3
"""Fill the corpus with every decision answer an enricher declares, then print coverage.

For every recipe this asks the decision model only what is missing or stale — one request per recipe,
carrying every question across every enricher — and stores each answer beside the corpus (F1/#162's ANSWER
items in dynamo mode, the answers JSONL in blob mode). A second run does nothing.

The decision model is a paid external service, so this needs OPENROUTER_API_KEY in the environment. That
is also why it is a tool for developers and the owner, not a Lambda: `make enrich-corpus` runs it against
the local corpus only, and a table or bucket whose name contains "prod" is refused unless
`--i-am-the-owner` is passed. Run it after a corpus import, a question rewording or a model bump.

    # what would be asked, without calling the model (no API key needed)
    uv run python scripts/enrich_corpus.py --local .cache/glean_recipe_cache --dry-run
    # fill the local/dev corpus
    uv run python scripts/enrich_corpus.py --local .cache/glean_recipe_cache
    # the owner's prod run, from the recipe-cache bucket into the recipes table
    uv run python scripts/enrich_corpus.py --table glean-recipes-prod \\
        --bucket glean-recipe-cache-prod-<account> --i-am-the-owner

Exits 1 unless every recipe has a current answer to every question: an unasked dietary question excludes
the recipe, so full coverage is the deploy gate.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import SecretStr

from glean.decisions import DecisionClient
from glean.recipes.corpus import open_corpus
from glean.recipes.enrichment import ENRICHERS, CorpusUnavailableError, EnrichmentError, run_enrichment

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.enrichment import Enricher


class OwnerApprovalError(Exception):
    """A prod table or bucket was named without the owner saying so."""


def main(
    argv: Sequence[str] | None = None,
    *,
    client: DecisionClient | None = None,
    corpus: RecipeCorpusStore | None = None,
) -> int:
    args = _parse_args(argv)
    try:
        _refuse_prod(args.table, args.bucket, i_am_the_owner=args.i_am_the_owner, writes=not args.dry_run)
        enrichers = _enrichers(args.enricher)
    except (OwnerApprovalError, EnrichmentError) as error:
        print(f"Refusing to run: {error}")
        return 2

    corpus = (
        corpus
        if corpus is not None
        else open_corpus(table=args.table, bucket=args.bucket, cache_dir=args.local, region=args.region)
    )
    # A dry run asks the model nothing, so it must not need a key the model would be billed to.
    client = client or (None if args.dry_run else _client(timeout_s=args.timeout))
    try:
        report = run_enrichment(
            corpus,
            client,
            enrichers=enrichers,
            dry_run=args.dry_run,
            max_workers=args.workers,
            limit=args.limit,
        )
    except CorpusUnavailableError as exc:
        print(f"FAILED: {exc}. Run scripts/build_recipe_index.py if the recipes exist but the index doesn't.")
        return 2
    print(report.render())
    if args.dry_run:
        return 0
    return 0 if report.coverage == 1.0 else 1


def _enrichers(selected: Sequence[str]) -> tuple[Enricher, ...]:
    """The enrichers to run: every registered one, or just the named ones, in registry order."""
    if not selected:
        return tuple(ENRICHERS.values())
    unknown = [name for name in selected if name not in ENRICHERS]
    if unknown:
        known = ", ".join(sorted(ENRICHERS)) or "none"
        raise EnrichmentError(f"no enricher called {', '.join(unknown)}; this build has: {known}")
    return tuple(enricher for name, enricher in ENRICHERS.items() if name in selected)


def _client(*, timeout_s: float) -> DecisionClient:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY to the OpenRouter key decision calls are billed to.")
    return DecisionClient(api_key=SecretStr(api_key), timeout_s=timeout_s)


def _refuse_prod(table: str | None, bucket: str | None, *, i_am_the_owner: bool, writes: bool = True) -> None:
    """A prod table or bucket is off limits unless the owner says so. A dry run writes nothing, so it may look.

    Both are checked: in blob mode the run rewrites the answers JSONL in the corpus prefix, so a prod
    bucket is as much a write as a prod table.
    """
    if not writes or i_am_the_owner:
        return
    named = [name for name in (table, bucket) if name and "prod" in name.casefold()]
    if named:
        raise OwnerApprovalError(
            f"{', '.join(named)} looks like a prod target; pass --i-am-the-owner once you have the owner's approval"
        )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask the decision model everything the corpus is missing.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bucket", help="S3 recipe-cache bucket: the corpus/ prefix, or the projection with --table.")
    source.add_argument("--local", type=Path, help="Local cache root holding corpus/: the local/dev corpus.")
    parser.add_argument("--table", help="DynamoDB recipes table (F1/#162): store the answers as items.")
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent decision requests.")
    parser.add_argument("--limit", type=int, default=None, help="Ask about the first N recipes (a smoke run).")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be asked, call and write nothing.")
    parser.add_argument(
        "--enricher",
        action="append",
        default=[],
        metavar="NAME",
        help=f"Only this enricher (repeatable). This build has: {', '.join(sorted(ENRICHERS))}.",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for each answer.")
    parser.add_argument(
        "--i-am-the-owner",
        action="store_true",
        help="Required to write a table or bucket whose name contains prod. Prod runs are the owner's.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
