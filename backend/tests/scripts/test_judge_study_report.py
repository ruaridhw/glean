from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.report import Narrative, build_report
from judge_study.results import Failure, Judgement, OutputItem, Results

SECTION_IDS = ["verdict", "agreement", "disagreements", "confidence", "operations", "recommendation"]


def _judged(
    item_id: str,
    feature: str = "meal_plan",
    *,
    panel: tuple[int, int] = (4, 4),
    llm: int = 4,
    decision: int = 4,
    confidence: float = 0.9,
    origin: str = "production",
    output: dict | None = None,
) -> OutputItem:
    def j(name: str, score: int, **extra: object) -> Judgement:
        return Judgement(
            judge=name, repeat=1, score=score, model=f"model-{name}", latency_s=1.0, cost_usd=0.001, **extra
        )  # type: ignore[arg-type]

    return OutputItem(
        item_id=item_id,
        feature=feature,  # type: ignore[arg-type]
        origin=origin,  # type: ignore[arg-type]
        input={"text": f"input of {item_id}"},
        output=output or {"title": f"output of {item_id}"},
        judge_inputs={},
        judgements=[
            j("llm", llm),
            j("decision", decision, confidence=confidence),
            j("panel_claude", panel[0]),
            j("panel_gpt", panel[1]),
        ],
    )


def _results() -> Results:
    items = [
        _judged("meal_plan/0/0"),
        _judged("meal_plan/1/0", llm=5, decision=3, panel=(4, 4)),  # judges split; decision off by one
        _judged("recipe_import/0/0", "recipe_import", panel=(2, 4), llm=3, decision=4),  # contested
        _judged("receipt_scan/0/0+stress", "receipt_scan", origin="stress", panel=(2, 2), llm=2, decision=2),
    ]
    return Results(
        models={"decision:meal_plan": "typesafe/jev-1.14-20261014", "llm:meal_plan": "z-ai/glm-5.2"},
        items=items,
        failures=[Failure(judge="llm", item_id="meal_plan/0/0", repeat=2, error="OutputParserException: empty")],
    )


NARRATIVE = Narrative(verdict="VERDICT-TEXT", recommendation="RECOMMENDATION-TEXT", notes=["NOTE-TEXT about taxonomy"])


def _page(results: Results | None = None) -> str:
    return build_report(results or _results(), NARRATIVE)


def _position(page: str, section: str) -> int:
    match = re.search(rf'<section[^>]*id="{section}"', page)
    assert match, f"no section {section}"
    return match.start()


class TestReportStructure:
    def test_sections_come_in_the_order_the_issue_lists_and_it_ends_with_the_recommendation(self) -> None:
        page = _page()

        positions = [_position(page, section) for section in SECTION_IDS]

        assert positions == sorted(positions)
        assert "RECOMMENDATION-TEXT" in page[positions[-1] :]

    def test_the_page_is_one_offline_file_with_no_external_resources(self) -> None:
        page = _page()

        assert not re.search(r"""(src|href)=["']https?:""", page)
        assert "@import" not in page
        assert not re.search(r"url\(\s*['\"]?https?:", page)

    def test_the_narrative_verdict_and_notes_are_shown(self) -> None:
        page = _page()

        assert "VERDICT-TEXT" in page
        assert "NOTE-TEXT about taxonomy" in page

    def test_content_from_outputs_is_escaped(self) -> None:
        results = _results()
        results.items[1] = _judged("meal_plan/1/0", llm=5, decision=3, output={"title": "<script>alert(1)</script>"})

        page = _page(results)

        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


class TestReportContent:
    def test_agreement_with_the_panel_is_given_for_both_judges_overall_and_per_feature(self) -> None:
        page = _page()
        agreement = page[_position(page, "agreement") : _position(page, "disagreements")]

        assert "Meal plan" in agreement
        assert "Receipt scan" in agreement
        assert "Production outputs only" in agreement
        assert "kappa" in agreement.lower()

    def test_contested_outputs_are_listed_apart_with_both_panel_scores(self) -> None:
        page = _page()
        gallery = page[_position(page, "disagreements") : _position(page, "confidence")]

        assert "Contested" in gallery
        contested = gallery[gallery.index("Contested") :]
        assert "recipe_import/0/0" in contested

    def test_the_gallery_shows_each_judges_score_beside_the_input_and_output(self) -> None:
        page = _page()
        gallery = page[_position(page, "disagreements") : _position(page, "confidence")]

        card = gallery[gallery.index("meal_plan/1/0") :]
        assert "input of meal_plan/1/0" in card
        assert "output of meal_plan/1/0" in card
        for judge in ("Existing LLM judge", "Decision judge", "Panel (Claude)", "Panel (GPT)"):
            assert judge in card

    def test_the_confidence_section_holds_a_chart_and_its_numbers(self) -> None:
        page = _page()
        section = page[_position(page, "confidence") : _position(page, "operations")]

        assert "<svg" in section
        assert "<table" in section

    def test_parse_failures_cost_and_latency_are_reported_per_judge(self) -> None:
        page = _page()
        operations = page[_position(page, "operations") : _position(page, "recommendation")]

        assert "Parse failures" in operations
        assert "p95" in operations
        assert "Drift" in operations
        assert "$" in operations
