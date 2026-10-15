"""The one-file offline HTML report. Everything it shows is computed from the results file."""

from __future__ import annotations

import html
import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from judge_study.features import FEATURES
from judge_study.metrics import (
    LEVELS,
    Agreement,
    agreement,
    agreement_with_panel,
    confusion_matrix,
    cost_summary,
    drift,
    item_score,
    judge_pairs,
    latency_summary,
    panel_reference,
    reliability_bins,
)

if TYPE_CHECKING:
    from judge_study.results import OutputItem, Results

CANDIDATES = {"decision": "Decision judge", "llm": "Existing LLM judge"}
LABELS = {
    "llm": "Existing LLM judge",
    "decision": "Decision judge",
    "panel_claude": "Panel (Claude)",
    "panel_gpt": "Panel (GPT)",
}


@dataclass(frozen=True)
class Narrative:
    """The author's reading of the numbers: the report computes the figures, a person writes the judgement."""

    verdict: str
    recommendation: str
    notes: list[str]


def _e(value: object) -> str:
    return html.escape(str(value))


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _kappa(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _usd(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:.2f}" if value >= 1 else f"${value:.5f}".rstrip("0").rstrip(".") if value else "$0"


def _seconds(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f} s"


def _paragraphs(text: str) -> str:
    return "".join(f"<p>{_e(block.strip())}</p>" for block in text.split("\n\n") if block.strip())


def _pips(score: int | None) -> str:
    if score is None:
        return '<span class="pips none" aria-label="no score">—</span>'
    cells = "".join(f'<i class="{"on" if n <= score else ""}"></i>' for n in range(1, LEVELS + 1))
    return f'<span class="pips" role="img" aria-label="score {score} of 5">{cells}<b>{score}</b></span>'


def _json(value: object) -> str:
    return _e(json.dumps(value, indent=2, ensure_ascii=False))


def _agreement_cells(result: Agreement) -> str:
    return f"<td>{result.n}</td><td>{_pct(result.exact)}</td><td>{_pct(result.within_one)}</td><td>{_kappa(result.kappa)}</td>"


def _verdict(results: Results, narrative: Narrative) -> str:
    items = results.items
    decision, llm = agreement_with_panel(items, "decision"), agreement_with_panel(items, "llm")
    decision_cost, llm_cost = cost_summary(items, "decision").mean, cost_summary(items, "llm").mean
    decision_p50, llm_p50 = latency_summary(items, "decision").p50, latency_summary(items, "llm").p50
    tiles = [
        (_pct(decision.exact), "decision judge matches the panel exactly", f"n = {decision.n}"),
        (_pct(llm.exact), "existing LLM judge matches the panel exactly", f"n = {llm.n}"),
    ]
    if decision_cost and llm_cost:
        tiles.append((f"{llm_cost / decision_cost:.0f}×", "cheaper per judgement with the decision judge", ""))
    if decision_p50 and llm_p50:
        tiles.append((f"{llm_p50 / decision_p50:.0f}×", "faster at the median", "p50 latency"))
    tile_html = "".join(
        f'<div class="tile"><strong>{v}</strong><span>{_e(a)}</span><em>{_e(b)}</em></div>' for v, a, b in tiles
    )
    judges = {}
    for item in items:
        for j in item.judgements:
            judges.setdefault(j.judge, set()).add(j.model)
    model_rows = "".join(
        f"<li><b>{_e(LABELS[name])}</b>: {_e(', '.join(sorted(models)))}</li>"
        for name, models in sorted(judges.items())
    )
    production = sum(i.origin == "production" for i in items)
    notes = "".join(f"<li>{_e(note)}</li>" for note in narrative.notes)
    return f"""<section id="verdict"><h2>Verdict</h2>
{_paragraphs(narrative.verdict)}
<div class="tiles">{tile_html}</div>
<details><summary>How the study was run, and what to keep in mind</summary>
<ul>
<li><b>{len(items)} outputs</b> are judged: {production} production outputs from the five features' own prompts, and
{len(items) - production} <i>stress</i> copies, deliberately degraded versions that put low scores in the mix.</li>
<li><b>Reference.</b> The maintainer chose not to score, so two strong judges scored every output blind on the same
rubric. The reference is their mean when they are within one point. Outputs they split by two or more are
<i>contested</i>: reported on their own and left out of every agreement figure.</li>
<li><b>Exact</b> means a judge equals one of the two panel scores. <b>Within one</b> means it is within a point of one.
<b>Kappa</b> is quadratically weighted, against the reference with a half point rounded up; it is shown as — when
there is no spread to agree about.</li>
<li>Each candidate judge ran three times per output; its score for an output is the median.</li>
<li>Models used: <ul>{model_rows}</ul></li>
{notes}
</ul></details></section>"""


def _feature_filter(items: list[OutputItem], feature: str) -> list[OutputItem]:
    return [item for item in items if item.feature == feature]


def _matrix(items: list[OutputItem], candidate: str) -> str:
    pairs = []
    for item in items:
        reference, score = panel_reference(item).score, item_score(item, candidate)  # type: ignore[arg-type]
        if reference is not None and score is not None:
            pairs.append((score, math.floor(reference + 0.5)))
    matrix = confusion_matrix(pairs)
    peak = max((count for row in matrix for count in row), default=0) or 1
    head = "".join(f"<th>{level}</th>" for level in range(1, LEVELS + 1))
    rows = "".join(
        f"<tr><th>{level}</th>"
        + "".join(
            f'<td style="--heat:{count / peak:.2f}"{" class=diag" if level == col else ""}>{count or ""}</td>'
            for col, count in enumerate(row, start=1)
        )
        + "</tr>"
        for level, row in enumerate(matrix, start=1)
    )
    return f'<table class="matrix"><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table>'


def _agreement(results: Results) -> str:
    items = results.items
    production = [item for item in items if item.origin == "production"]
    summary = ""
    for label, subset in (("All outputs", items), ("Production outputs only", production)):
        cells = "".join(_agreement_cells(agreement_with_panel(subset, name)) for name in CANDIDATES)  # type: ignore[arg-type]
        summary += f"<tr><th scope='row'>{label}</th>{cells}</tr>"
    inter = [
        ("The two panel judges, one another", agreement(judge_pairs(items, "panel_claude", "panel_gpt"))),
        ("Decision judge and existing LLM judge, one another", agreement(judge_pairs(items, "llm", "decision"))),
    ]
    inter_rows = "".join(f"<tr><th scope='row'>{_e(label)}</th>{_agreement_cells(a)}</tr>" for label, a in inter)
    per_feature = ""
    matrices = ""
    for feature, spec in FEATURES.items():
        subset = _feature_filter(items, feature)
        cells = "".join(_agreement_cells(agreement_with_panel(subset, name)) for name in CANDIDATES)  # type: ignore[arg-type]
        per_feature += f"<tr><th scope='row'>{_e(spec.label)}</th>{cells}</tr>"
        matrices += (
            f"<div class='pair'><h4>{_e(spec.label)}</h4><div class='mats'>"
            + "".join(
                f"<figure><figcaption>{_e(label)}</figcaption>{_matrix(subset, name)}</figure>"
                for name, label in CANDIDATES.items()
            )
            + "</div></div>"
        )
    group = (
        "<tr><td></td>"
        + "".join(f"<th colspan='4' scope='colgroup'>{_e(label)}</th>" for label in CANDIDATES.values())
        + "</tr>"
    )
    cols = "<tr><td></td>" + "<th>n</th><th>Exact</th><th>Within one</th><th>Kappa</th>" * len(CANDIDATES) + "</tr>"
    return f"""<section id="agreement"><h2>Agreement per feature</h2>
<p class="lede">Each candidate judge against the panel reference.</p>
<div class="scroll"><table class="grid"><thead>{group}{cols}</thead><tbody>{summary}{per_feature}</tbody></table></div>
<p class="small">Per-feature kappa rests on a handful of outputs per feature; read it as a direction, not a measurement.</p>
<h3>Judges against each other</h3>
<div class="scroll"><table class="grid"><thead><tr><td></td><th>n</th><th>Exact</th><th>Within one</th><th>Kappa</th></tr></thead>
<tbody>{inter_rows}</tbody></table></div>
<details><summary>Confusion matrices per feature (rows: the candidate's score, columns: the panel reference)</summary>
{matrices}</details></section>"""


def _card(item: OutputItem) -> str:
    spec = FEATURES[item.feature]
    scores = "".join(
        f"<div><span>{_e(label)}</span>{_pips(item_score(item, name))}</div>"  # type: ignore[arg-type]
        for name, label in LABELS.items()
    )
    tag = '<span class="tag">stress copy</span>' if item.origin == "stress" else ""
    return f"""<article class="card"><header><code>{_e(item.item_id)}</code> <span>{_e(spec.label)}</span>{tag}</header>
<div class="scores">{scores}<div><span>Maintainer</span><span class="pips none">not scored</span></div></div>
<div class="io"><div><h4>Input</h4><pre>{_json(item.input)}</pre></div><div><h4>Output</h4><pre>{_json(item.output)}</pre></div></div></article>"""


def _gallery(results: Results) -> str:
    flagged: list[tuple[int, OutputItem]] = []
    contested: list[OutputItem] = []
    for item in results.items:
        reference = panel_reference(item)
        if reference.contested:
            contested.append(item)
            continue
        llm, decision = item_score(item, "llm"), item_score(item, "decision")
        panel = (item_score(item, "panel_claude"), item_score(item, "panel_gpt"))
        misses = [s for s in (llm, decision) if s is not None and s not in panel]
        split = llm is not None and decision is not None and llm != decision
        if split or misses:
            gap = abs(llm - decision) if split and llm and decision else 1
            flagged.append((gap, item))
    flagged.sort(key=lambda pair: -pair[0])
    body = "".join(_card(item) for _, item in flagged) or "<p>The judges and the panel never disagreed.</p>"
    contested_html = (
        "".join(_card(item) for item in contested)
        if contested
        else "<p>The two panel judges never differed by two or more points.</p>"
    )
    return f"""<section id="disagreements"><h2>Disagreement gallery</h2>
<p class="lede">Every output where the two candidate judges differ, or where one differs from both panel judges.
{len(flagged)} of {len(results.items)} outputs, widest gap first.</p>
{body}
<h3>Contested by the panel</h3>
<p class="small">The panel judges differ by two or more points, so there is no reference; these are excluded from the figures above.</p>
{contested_html}</section>"""


def _chart(bins: list) -> str:
    size, pad = 320, 40
    inner = size - 2 * pad

    def x(v: float) -> float:
        return pad + v * inner

    def y(v: float) -> float:
        return size - pad - v * inner

    grid = "".join(
        f'<line x1="{x(v)}" y1="{y(0)}" x2="{x(v)}" y2="{y(1)}" class="g"/><line x1="{x(0)}" y1="{y(v)}" x2="{x(1)}" y2="{y(v)}" class="g"/>'
        f'<text x="{x(v)}" y="{size - pad + 16}" text-anchor="middle">{v:.1f}</text><text x="{pad - 8}" y="{y(v) + 4}" text-anchor="end">{v:.1f}</text>'
        for v in (0, 0.25, 0.5, 0.75, 1)
    )
    points = "".join(
        f'<circle cx="{x(b.mean_confidence):.1f}" cy="{y(b.accuracy):.1f}" r="{5 + 2.5 * math.sqrt(b.n):.1f}" class="pt"><title>{b.n} outputs</title></circle>'
        f'<text x="{x(b.mean_confidence):.1f}" y="{y(b.accuracy) - 12 - 2.5 * math.sqrt(b.n):.1f}" text-anchor="middle" class="n">{b.n}</text>'
        for b in bins
    )
    return (
        f'<svg viewBox="0 0 {size} {size}" role="img" aria-label="Reliability chart: accuracy against confidence">{grid}'
        f'<line x1="{x(0)}" y1="{y(0)}" x2="{x(1)}" y2="{y(1)}" class="diag"/>{points}'
        f'<text x="{size / 2}" y="{size - 4}" text-anchor="middle" class="ax">mean confidence of the decision judge</text>'
        f'<text transform="translate(12 {size / 2}) rotate(-90)" text-anchor="middle" class="ax">share matching the panel</text></svg>'
    )


def _confidence(results: Results) -> str:
    bins = reliability_bins(results.items, bins=5, reference="panel")
    if not bins:
        return '<section id="confidence"><h2>Does confidence track correctness?</h2><p>No outputs had both a confidence and a panel reference.</p></section>'
    rows = "".join(
        f"<tr><th scope='row'>{b.lower:.1f}–{b.upper:.1f}</th><td>{b.n}</td><td>{b.mean_confidence:.2f}</td><td>{_pct(b.accuracy)}</td></tr>"
        for b in bins
    )
    return f"""<section id="confidence"><h2>Does confidence track correctness?</h2>
<p class="lede">The decision judge reports how sure it is. If that is meaningful, outputs it is more sure about should match
the panel more often. Points on the dashed line mean confidence equals accuracy; points below it mean overconfidence.
Bubble size and label are the number of outputs.</p>
<div class="chart">{_chart(bins)}
<table class="grid"><thead><tr><th>Confidence</th><th>Outputs</th><th>Mean confidence</th><th>Matches panel</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="small">Each output's confidence is the mean over its three repeats; "matches" means equalling either panel score.
Contested outputs are left out. The maintainer's own scores were not collected, so this is the panel's view of correctness.</p></section>"""


def _operations(results: Results) -> str:
    items = results.items
    rows = ""
    for name, label in LABELS.items():
        cost, latency = cost_summary(items, name), latency_summary(items, name)  # type: ignore[arg-type]
        stability = drift(items, name) if name in CANDIDATES else None  # type: ignore[arg-type]
        failed = sum(f.judge == name for f in results.failures)
        stable = (
            "—"
            if stability is None or stability.identical_share is None
            else f"{_pct(stability.identical_share)} identical, widest spread {stability.max_range}"
        )
        rows += (
            f"<tr><th scope='row'>{_e(label)}</th><td>{cost.judgements}</td><td>{_usd(cost.mean)}</td><td>{_usd(cost.total)}</td>"
            f"<td>{_seconds(latency.p50)}</td><td>{_seconds(latency.p95)}</td><td>{_e(stable)}</td><td>{failed}</td></tr>"
        )
    failures = "".join(
        f"<li><code>{_e(f.item_id)}</code> ({_e(LABELS[f.judge])}, repeat {f.repeat}): {_e(f.error)}</li>"
        for f in results.failures
    )
    total = sum(j.cost_usd or 0 for item in items for j in item.judgements)
    return f"""<section id="operations"><h2>Drift, cost and latency</h2>
<div class="scroll"><table class="grid"><thead><tr><th>Judge</th><th>Judgements</th><th>Cost each</th><th>Cost total</th><th>p50</th><th>p95</th>
<th>Drift across repeats</th><th>Parse failures</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="small">Drift is how often a judge's three repeats on one output gave the same score; only the candidates were repeated.
Decision-judge cost is the cost the endpoint reports. LLM-judge cost is the reported tokens at OpenRouter's list price, because its
generation-stats endpoint does not list these calls. Calls ran three at a time, so latency includes some queueing for every judge alike.</p>
{"<h3>Parse failures</h3><ul>" + failures + "</ul>" if failures else ""}
<p class="small">Whole study spend across all judgements shown: {_usd(total)} (excluding the cost of freezing the outputs).</p></section>"""


_CSS = """
:root{--bg:#f6f2ea;--paper:#fffdf8;--ink:#201d18;--mute:#6a6459;--line:#d8d0c0;--accent:#1d5c63;--hot:#b4472a;--good:#2f6b3a;--pip:#e6dfd0}
@media (prefers-color-scheme:dark){:root{--bg:#141310;--paper:#1c1a16;--ink:#ece6d8;--mute:#a39b8b;--line:#3a352b;--accent:#6cc1c9;--hot:#e58a6b;--good:#7fc48b;--pip:#332f26}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 Georgia,'Iowan Old Style',serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:clamp(28px,5vw,44px);line-height:1.1;margin:.2em 0}
h2{font-size:26px;margin:0 0 .4em;padding-top:.2em}
h3{font-size:19px;margin:1.6em 0 .3em}
h4{font:600 12px/1 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--mute);margin:.8em 0 .3em}
section{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:22px 0}
.kicker{font:600 12px/1 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.12em;color:var(--accent)}
.lede{color:var(--mute)}.small{font-size:14px;color:var(--mute)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:16px 0}
.tile{border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile strong{display:block;font:700 34px/1.1 ui-monospace,Menlo,monospace;color:var(--accent)}
.tile span{display:block;font-size:14px}.tile em{font-size:12px;color:var(--mute);font-style:normal}
table{border-collapse:collapse;width:100%;font:14px/1.4 system-ui,sans-serif}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left}thead th{font-weight:600;color:var(--mute)}
.scroll{overflow-x:auto}
.card{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:14px 0}
.card header{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font:14px system-ui,sans-serif}
.tag{background:var(--hot);color:var(--paper);border-radius:99px;padding:1px 9px;font-size:12px}
.scores{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0;font:13px system-ui,sans-serif}
.scores span:first-child{display:block;color:var(--mute);font-size:12px}
.pips{display:inline-flex;gap:3px;align-items:center}.pips i{width:13px;height:13px;background:var(--pip);border-radius:3px}
.pips i.on{background:var(--accent)}.pips b{margin-left:6px;font-family:ui-monospace,monospace}.pips.none{color:var(--mute)}
.io{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
pre{white-space:pre-wrap;word-break:break-word;margin:0;max-height:260px;overflow:auto;font:12.5px/1.45 ui-monospace,Menlo,monospace;background:var(--bg);padding:8px;border-radius:6px}
.mats{display:flex;gap:18px;flex-wrap:wrap}.matrix{width:auto}.matrix td{text-align:center;min-width:30px;background:color-mix(in srgb,var(--accent) calc(var(--heat,0)*70%),transparent)}
.matrix td.diag{outline:1px solid var(--accent)}
figure{margin:0}figcaption{font:12px system-ui,sans-serif;color:var(--mute)}
.chart{display:grid;grid-template-columns:minmax(260px,340px) 1fr;gap:20px;align-items:center}
@media (max-width:700px){.chart{grid-template-columns:1fr}}
svg{width:100%;height:auto}svg text{fill:var(--mute);font:11px system-ui,sans-serif}svg .g{stroke:var(--line);stroke-width:1}
svg .diag{stroke:var(--mute);stroke-dasharray:5 4}svg .pt{fill:var(--accent);fill-opacity:.55;stroke:var(--accent)}svg .n{fill:var(--ink)}
details{margin-top:12px}summary{cursor:pointer;font:600 14px system-ui,sans-serif;color:var(--accent)}
code{font-size:13px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media print{body{background:#fff}section{break-inside:avoid-page}}
"""


def build_report(results: Results, narrative: Narrative) -> str:
    sections = [
        _verdict(results, narrative),
        _agreement(results),
        _gallery(results),
        _confidence(results),
        _operations(results),
        f'<section id="recommendation"><h2>Recommendation</h2>{_paragraphs(narrative.recommendation)}</section>',
    ]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decision model as eval judge</title><style>{_CSS}</style></head>
<body><main>
<p class="kicker">Glean evals · issue #124</p>
<h1>Can the decision model judge our evals?</h1>
{"".join(sections)}
</main></body></html>
"""
