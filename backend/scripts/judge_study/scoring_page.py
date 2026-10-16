"""Judge (c): a small page where the maintainer scores outputs without seeing either judge's score."""

from __future__ import annotations

import html
import json
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

from judge_study.features import FEATURES

if TYPE_CHECKING:
    from pathlib import Path

    from judge_study.results import OutputItem


def select_for_scoring(items: list[OutputItem], count: int, seed: int) -> list[OutputItem]:
    """`count` outputs spread across the features: small features whole, the rest evenly shared."""
    if len(items) <= count:
        return items
    by_feature: dict[str, list[OutputItem]] = {}
    for item in items:
        by_feature.setdefault(item.feature, []).append(item)
    rng = random.Random(seed)  # noqa: S311
    pools = {feature: rng.sample(pool, len(pool)) for feature, pool in by_feature.items()}
    chosen: dict[str, list[OutputItem]] = {feature: [] for feature in pools}
    remaining = count
    while remaining and any(pools.values()):
        for feature, pool in pools.items():
            if remaining and pool:
                chosen[feature].append(pool.pop())
                remaining -= 1
    picked = {item.item_id for taken in chosen.values() for item in taken}
    return [item for item in items if item.item_id in picked]


def _read_scores(path: Path) -> dict[str, int]:
    return json.loads(path.read_text()) if path.exists() else {}


_CSS = """
:root { --bg:#fbfaf7; --fg:#1d1d1b; --card:#fff; --line:#d9d6cc; --accent:#1f6f4a; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161614; --fg:#ecebe6; --card:#20201d; --line:#3a3a35; --accent:#6fd3a0; }
}
body { margin:0; padding:16px; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui, sans-serif; }
main { max-width:760px; margin:0 auto; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:16px 0; }
pre { white-space:pre-wrap; word-break:break-word; margin:4px 0 12px; font:13px/1.45 ui-monospace, monospace; }
h2 { font-size:18px; margin:4px 0; }
h3 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; margin:8px 0 0; opacity:.7; }
.choices { display:flex; gap:20px; padding:8px 0; font-size:20px; }
.choices input { width:22px; height:22px; accent-color:var(--accent); }
#progress { position:sticky; top:0; padding:8px 0; background:var(--bg); font-weight:600; }
"""


def _render(items: list[OutputItem], scores: dict[str, int]) -> str:
    cards = []
    for number, item in enumerate(items, start=1):
        spec = FEATURES[item.feature]
        current = scores.get(item.item_id)
        choices = "".join(
            f'<label><input type="radio" name="{html.escape(item.item_id)}" value="{value}"'
            f"{' checked' if current == value else ''}> {value}</label>"
            for value in range(1, 6)
        )
        cards.append(
            f'<section class="card" data-id="{html.escape(item.item_id)}">'
            f"<h2>{number}. {html.escape(spec.label)}</h2>"
            f"<h3>Input</h3><pre>{html.escape(json.dumps(item.input, indent=2, ensure_ascii=False))}</pre>"
            f"<h3>Output</h3><pre>{html.escape(json.dumps(item.output, indent=2, ensure_ascii=False))}</pre>"
            f"<details><summary>Rubric</summary><pre>{html.escape(spec.rubric)}</pre></details>"
            f'<div class="choices">{choices}</div></section>'
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Score the outputs</title>
<style>
{_CSS}
</style></head><body><main>
<p id="progress">{len([i for i in items if i.item_id in scores])} of {len(items)} scored</p>
<p>Score each output from 1 (bad) to 5 (perfect) against its rubric. Scores save as you click.</p>
{"".join(cards)}
</main>
<script>
const total = {len(items)};
document.addEventListener('change', async (event) => {{
  const input = event.target;
  const id = input.closest('.card').dataset.id;
  const response = await fetch('/score', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{item_id: id, score: Number(input.value)}})}});
  if (!response.ok) {{ alert('Could not save that score'); return; }}
  input.closest('.card').style.borderColor = 'var(--accent)';
  const done = document.querySelectorAll('.card input:checked').length;
  document.getElementById('progress').textContent = done + ' of ' + total + ' scored';
}});
</script></body></html>"""


def make_server(host: str, port: int, items: list[OutputItem], scores_path: Path) -> ThreadingHTTPServer:
    known = {item.item_id for item in items}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/scores":
                self._send(200, json.dumps(_read_scores(scores_path)), "application/json")
            elif self.path == "/":
                self._send(200, _render(items, _read_scores(scores_path)), "text/html; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self) -> None:
            if self.path != "/score":
                self._send(404, "not found", "text/plain")
                return
            try:
                payload: Any = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                item_id, score = payload["item_id"], payload["score"]
            except (ValueError, KeyError, TypeError):
                self._send(400, "bad request", "text/plain")
                return
            if item_id not in known or isinstance(score, bool) or score not in range(1, 6):
                self._send(400, "unknown item or score outside 1-5", "text/plain")
                return
            scores = _read_scores(scores_path)
            scores[item_id] = score
            scores_path.write_text(json.dumps(scores, indent=2) + "\n")
            self._send(200, "{}", "application/json")

        def _send(self, status: int, body: str, content_type: str) -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    return ThreadingHTTPServer((host, port), Handler)
