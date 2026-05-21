#!/usr/bin/env python3
"""Diagnostic script: compare create_chat_model() vs OpenRouter() directly.

Run from backend/:
    uv run python scripts/simple_llm.py          # all tests
    uv run python scripts/simple_llm.py --test 5  # single test

Each test runs in its own subprocess (via --test N) so a hang in one doesn't
block the rest. All prints are flushed immediately.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage
from langchain_openrouter import ChatOpenRouter
from openrouter import OpenRouter

from glean.llm import create_chat_model

_ENV = dotenv_values(Path(__file__).parent.parent / ".env")
API_KEY = _ENV.get("OPENROUTER_API_KEY", "")
MODEL = _ENV.get("LLM_MODEL") or "google/gemma-3-4b-it:free"
PROMPT = "Reply with exactly one word: pong"
TIMEOUT = 20  # seconds per test

TESTS = {
    1: "openrouter SDK — client.chat.send()",
    2: "create_chat_model() → .invoke()",
    3: "ChatOpenRouter() directly → .invoke()",
    4: "ChatOpenRouter(streaming=False) → .invoke()",
    5: "httpx directly to openrouter.ai",
    6: "ChatOpenRouter(max_retries=0) → .invoke()",
    7: "openrouter SDK — models.list() only (no chat)",
}


# ── Single-test execution (called by subprocess) ─────────────────────────────


def _run_single(n: int) -> None:
    """Run test N and print a single result line."""

    if n == 1:
        client = OpenRouter(api_key=API_KEY)
        resp = client.chat.send(
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT}],
        )
        print(resp.choices[0].message.content, flush=True)

    elif n == 2:
        model = create_chat_model(MODEL, api_key=API_KEY)
        print(f"[type={type(model).__name__}]", flush=True)
        response = model.invoke([HumanMessage(content=PROMPT)])
        print(response.content, flush=True)

    elif n == 3:
        model = ChatOpenRouter(model=MODEL, openrouter_api_key=API_KEY)
        response = model.invoke([HumanMessage(content=PROMPT)])
        print(response.content, flush=True)

    elif n == 4:
        model = ChatOpenRouter(model=MODEL, openrouter_api_key=API_KEY, streaming=False)
        response = model.invoke([HumanMessage(content=PROMPT)])
        print(response.content, flush=True)

    elif n == 5:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": PROMPT}]},
            timeout=15,
        )
        r.raise_for_status()
        print(r.json()["choices"][0]["message"]["content"], flush=True)

    elif n == 6:
        model = ChatOpenRouter(model=MODEL, openrouter_api_key=API_KEY, max_retries=0)
        response = model.invoke([HumanMessage(content=PROMPT)])
        print(response.content, flush=True)

    elif n == 7:
        client = OpenRouter(api_key=API_KEY)
        models = client.models.list()
        ids = [m.id for m in models.data[:3]]
        print(f"first 3 models: {ids}", flush=True)


# ── Orchestrator ─────────────────────────────────────────────────────────────


def _run_all(tests: list[int]) -> None:
    if not API_KEY.startswith("sk-or-"):
        print("ERROR: no real OPENROUTER_API_KEY in backend/.env", flush=True)
        sys.exit(1)

    print(f"Model : {MODEL}", flush=True)
    print(f"Key   : {API_KEY[:12]}...", flush=True)
    print(flush=True)

    script = Path(__file__)
    for n in tests:
        label = TESTS[n]
        print(f"{'─' * 60}", flush=True)
        print(f"  {n}. {label}", flush=True)
        print(f"{'─' * 60}", flush=True)
        t0 = time.perf_counter()
        try:
            result = subprocess.run(  # noqa: S603
                [sys.executable, str(script), "--test", str(n)],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
            elapsed = time.perf_counter() - t0
            out = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                print(f"  OK   {elapsed:.2f}s  →  {out!r}", flush=True)
            else:
                print(f"  ERR  {elapsed:.2f}s  →  {out}", flush=True)
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            print(f"  HANG timed out after {elapsed:.0f}s", flush=True)
        print(flush=True)


if __name__ == "__main__":
    if "--test" in sys.argv:
        n = int(sys.argv[sys.argv.index("--test") + 1])
        try:
            _run_single(n)
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            sys.exit(1)
    else:
        tests = list(TESTS.keys())
        _run_all(tests)
