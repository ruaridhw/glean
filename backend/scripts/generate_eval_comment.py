#!/usr/bin/env python3
"""Generate a jazzy GitHub PR comment from eval JUnit XML results."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class EvalResult:
    name: str
    classname: str
    passed: bool
    failure_message: str = ""


@dataclass
class FeatureResults:
    structural: list[EvalResult] = field(default_factory=list)
    heuristic: list[EvalResult] = field(default_factory=list)
    judge: list[EvalResult] = field(default_factory=list)


def parse_junit_xml(path: str) -> list[EvalResult]:
    results: list[EvalResult] = []
    try:
        tree = ET.parse(path)  # noqa: S314
    except (ET.ParseError, FileNotFoundError):
        return results
    for testcase in tree.iter("testcase"):
        failure = testcase.find("failure")
        results.append(
            EvalResult(
                name=testcase.get("name", ""),
                classname=testcase.get("classname", ""),
                passed=failure is None,
                failure_message=failure.get("message", "") if failure is not None else "",
            )
        )
    return results


def classify_results(results: list[EvalResult]) -> dict[str, FeatureResults]:
    features: dict[str, FeatureResults] = {
        "receipt-scan": FeatureResults(),
        "pantry-purchase-description": FeatureResults(),
        "meal-plan-generation": FeatureResults(),
        "shopping-list-description": FeatureResults(),
        "recipe-import": FeatureResults(),
    }
    for r in results:
        classname_lower = r.classname.lower()
        if "purchase_description" in classname_lower:
            feature = "pantry-purchase-description"
        elif "shopping_list_description" in classname_lower:
            feature = "shopping-list-description"
        elif "receipt" in classname_lower:
            feature = "receipt-scan"
        elif "suggestion" in classname_lower:
            feature = "meal-plan-generation"
        elif "recipe" in classname_lower:
            feature = "recipe-import"
        else:
            continue

        if "structural" in classname_lower:
            features[feature].structural.append(r)
        elif "heuristic" in classname_lower:
            features[feature].heuristic.append(r)
        elif "judge" in classname_lower:
            features[feature].judge.append(r)
    return features


def _score(results: list[EvalResult]) -> str:
    if not results:
        return "\u2014"
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    return f"{passed}/{total}"


def _pct(results: list[EvalResult]) -> str:
    if not results:
        return "\u2014"
    passed = sum(1 for r in results if r.passed)
    return f"{100 * passed // len(results)}%"


def _status_icon(results: list[EvalResult]) -> str:
    if not results:
        return "\u2b1c"
    return "\u2705" if all(r.passed for r in results) else "\u274c"


def _render_table(results: list[EvalResult], pass_icon: str, fail_icon: str) -> list[str]:
    lines = ["", "| Check | Status |", "|-------|--------|"]
    lines.extend(f"| {r.name} | {pass_icon if r.passed else fail_icon} |" for r in results)
    failures = [r for r in results if not r.passed]
    if failures:
        label = "**Failures:**" if fail_icon == "\u274c" else "**Issues:**"
        lines.append("")
        lines.append(label)
        lines.extend(f"- `{r.name}`: {r.failure_message}" for r in failures)
    return lines


def _detail_section(name: str, fr: FeatureResults) -> str:
    structural_score = _score(fr.structural)
    heuristic_score = _pct(fr.heuristic)
    judge_score = _pct(fr.judge)

    lines = [
        "<details>",
        f"<summary><strong>{name}</strong> \u2014 {structural_score} structural, "
        f"{heuristic_score} heuristic, {judge_score} judge</summary>",
        "",
        "### Structural (hard gate)",
    ]

    if not fr.structural:
        lines.append("No structural tests found.")
    elif all(r.passed for r in fr.structural):
        lines.append(f"All {len(fr.structural)} checks passed.")
    else:
        lines.extend(_render_table(fr.structural, "\u2705", "\u274c"))

    lines.extend(["", "### Heuristic (soft gate)"])
    if fr.heuristic:
        lines.extend(_render_table(fr.heuristic, "\u2705", "\u26a0\ufe0f"))
    else:
        lines.append("No heuristic tests found.")

    lines.extend(["", "### LLM Judge (soft gate)"])
    if fr.judge:
        for r in fr.judge:
            icon = "\u2705" if r.passed else "\u26a0\ufe0f"
            lines.append(f"- {icon} {r.name}")
            if not r.passed:
                lines.append(f"  - {r.failure_message}")
    else:
        lines.append("No judge tests found.")

    lines.extend(["", "</details>", ""])
    return "\n".join(lines)


def generate_comment(
    hard_results: list[EvalResult],
    soft_results: list[EvalResult],
    model: str,
) -> str:
    all_results = hard_results + soft_results
    features = classify_results(all_results)

    hard_passed = all(r.passed for r in hard_results) if hard_results else True
    soft_issues = [r for r in soft_results if not r.passed]

    lines = [
        f"## \U0001f9ea Eval Results \u2014 `{model}`",
        "",
        "| Feature | Structural | Heuristic | LLM Judge |",
        "|---------|:----------:|:---------:|:---------:|",
    ]

    for name, fr in features.items():
        s_icon = _status_icon(fr.structural)
        lines.append(f"| {name} | {s_icon} {_score(fr.structural)} | {_pct(fr.heuristic)} | {_pct(fr.judge)} |")

    lines.append("")
    if hard_passed:
        lines.append("**Hard gate:** \u2705 Passed \u2014 all structural checks passed")
    else:
        lines.append("**Hard gate:** \u274c Failed \u2014 structural checks have failures")

    if soft_issues:
        lines.append(f"**Soft gate:** \u26a0\ufe0f Advisory \u2014 {len(soft_issues)} soft check(s) flagged")
    else:
        lines.append("**Soft gate:** \u2705 All soft checks passed")

    lines.append("")
    lines.append("---")
    lines.append("")

    for name, fr in features.items():
        lines.append(_detail_section(name, fr))

    lines.append("---")
    lines.append("")
    lines.append("\U0001f517 View traces in LangSmith: `glean` project")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate eval PR comment from JUnit XML")
    parser.add_argument("--hard-gate", required=True, help="Path to hard-gate JUnit XML")
    parser.add_argument("--soft-gate", required=True, help="Path to soft-gate JUnit XML")
    parser.add_argument("--model", required=True, help="Model identifier for display")
    args = parser.parse_args()

    hard_results = parse_junit_xml(args.hard_gate)
    soft_results = parse_junit_xml(args.soft_gate)
    comment = generate_comment(hard_results, soft_results, args.model)
    sys.stdout.write(comment)


if __name__ == "__main__":
    main()
