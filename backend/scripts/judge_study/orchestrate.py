"""Run a batch of judging jobs with retries, keeping an account of every attempt."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Protocol

from judge_study.results import Failure

if TYPE_CHECKING:
    from collections.abc import Callable

    from judge_study.results import Attempt, Judgement, JudgeName, OutputItem, Results

type Job = tuple[str, JudgeName, int]
"""An output's id, the judge that should score it, and which repeat this is."""


class Judge(Protocol):
    def judge(self, item: OutputItem, repeat: int) -> Judgement: ...


type JudgeFactory = Callable[[JudgeName, OutputItem, list[Attempt]], Judge]


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {str(error)[:150]}"


def run_jobs(
    results: Results,
    jobs: list[Job],
    make_judge: JudgeFactory,
    *,
    workers: int = 3,
    max_attempts: int = 2,
    spend_cap: float | None = None,
) -> Results:
    """Obtain each job's judgement, retrying a failed call once, and return the updated results.

    Every call is logged in `attempts` whatever its outcome, so cost and latency include the failed ones. A job that
    fails every attempt becomes a `Failure`; running it again later replaces that failure. Judgements that already
    exist are never bought twice. Once the logged cost reaches `spend_cap`, no further job starts.
    """
    items = {item.item_id: item for item in results.items}
    pending = [
        job for job in jobs if not any(j.judge == job[1] and j.repeat == job[2] for j in items[job[0]].judgements)
    ]
    ledger: list[Attempt] = []
    obtained: list[tuple[str, Judgement]] = []
    failures: list[Failure] = []
    lock = threading.Lock()

    def spent() -> float:
        return sum(a.cost_usd or 0.0 for a in list(ledger))

    def run_one(job: Job) -> None:
        item_id, name, repeat = job
        item = items[item_id]
        last_error = ""
        for _ in range(max_attempts):
            if spend_cap is not None and spent() >= spend_cap:
                return
            try:
                judgement = make_judge(name, item, ledger).judge(item, repeat)
            except Exception as error:
                last_error = _describe(error)
                continue
            mine = [a for a in list(ledger) if (a.judge, a.item_id, a.repeat) == (name, item_id, repeat)]
            priced = [a.cost_usd for a in mine if a.cost_usd is not None]
            judgement = judgement.model_copy(
                update={
                    "attempts": len(mine),
                    "cost_usd": sum(priced) if priced else None,
                    "latency_s": sum(a.latency_s for a in mine),
                }
            )
            with lock:
                obtained.append((item_id, judgement))
            return
        if last_error:
            with lock:
                failures.append(Failure(judge=name, item_id=item_id, repeat=repeat, error=last_error))

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(run_one, pending))

    recovered = {(j.judge, item_id, j.repeat) for item_id, j in obtained}
    new_failures = {(f.judge, f.item_id, f.repeat) for f in failures}
    kept = [
        f
        for f in results.failures
        if (f.judge, f.item_id, f.repeat) not in recovered and (f.judge, f.item_id, f.repeat) not in new_failures
    ]
    by_item: dict[str, list[Judgement]] = {}
    for item_id, judgement in obtained:
        by_item.setdefault(item_id, []).append(judgement)
    updated = [
        item.model_copy(
            update={
                "judgements": sorted(
                    [*item.judgements, *by_item.get(item.item_id, [])], key=lambda j: (j.judge, j.repeat)
                )
            }
        )
        for item in results.items
    ]
    return results.model_copy(
        update={"items": updated, "failures": [*kept, *failures], "attempts": [*results.attempts, *ledger]}
    )
