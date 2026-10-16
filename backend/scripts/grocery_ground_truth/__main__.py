"""Print the retailer verdict and evidence for a processed ingredient.

uv run --group audit python -m scripts.grocery_ground_truth "korma curry paste" --n 5
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

from . import ContainsPolicy, Frequency, OcadoReader, ProductCache, SainsburysReader, ground_truth, is_unsafe
from .browser import PlaywrightPageSource

DEFAULT_CACHE_DIR = Path(__file__).parents[2] / ".cache" / "grocery_ground_truth"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ingredient")
    parser.add_argument("--n", type=int, default=5, help="Read this many products.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--refetch-after-days", type=int, default=30)
    parser.add_argument("--minimum", choices=[f.value for f in Frequency], default=Frequency.USUALLY.value)
    parser.add_argument("--may-contain-counts", action="store_true", help="Count 'may contain' warnings as containing.")
    args = parser.parse_args(argv)
    policy = ContainsPolicy(minimum=Frequency(args.minimum), may_contain_counts=args.may_contain_counts)
    cache = ProductCache(args.cache_dir, max_age=timedelta(days=args.refetch_after_days))
    with PlaywrightPageSource() as source:
        verdict = ground_truth(
            args.ingredient, args.n, readers=[OcadoReader(source), SainsburysReader(source)], cache=cache
        )
    print(f"{verdict.ingredient}: {verdict.status}" + (f" via {verdict.retailer}" if verdict.retailer else ""))
    if verdict.status == "resolved":
        print(f"  products read: {verdict.products_read}")
        print(f"  tree nut as ingredient: {verdict.tree_nut} ({verdict.tree_nut_products})")
        print(f"  peanut as ingredient: {verdict.peanut} ({verdict.peanut_products})")
        print(f"  may contain nuts: {verdict.may_contain} ({verdict.may_contain_products}, kept separate)")
        print(f"  contains under the policy: {is_unsafe(verdict, policy)}")
        for item in verdict.evidence:
            print(f"  - [{item.kind}] {item.product_name} {item.url}\n      {item.quote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
