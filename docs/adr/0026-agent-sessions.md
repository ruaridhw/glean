---
status: accepted
date: 2026-10-22
---

# Agent sessions are the backend's one transient per-user state, and the session's own lease is their liveness

Generating a week became an agent run: too slow for the 30 s Lambda/API Gateway cap, and — from V3 —
something the household can watch and answer. So `POST /meal-plan/sessions` writes one item to
DynamoDB and returns `202 {session_id}`; a worker runs the agent; the app polls
`GET /meal-plan/sessions/{id}`. Everything below already holds in V1 (the plumbing), which wraps
today's corpus pipeline: `prepare → plan → finalise`.

**One item, one user, one day.** `agent_sessions` is keyed `pk=<Cognito sub>`, `sk=<session id>`, so
another household's session is unreachable by key rather than hidden by a check. The item holds the
inputs, the status, a bounded list of progress lines (the poll cursor is an index into it) and then
either the plan or a typed error `code`. Every update refreshes a 24 h TTL. `GET` never writes,
because the app calls it every second. This is the only transient per-user state the backend keeps:
everything else the app owns stays on the device.

**The agent is a deep module.** `glean.agent` exposes `start(session)` — `resume` and `cancel` arrive
with the routes that call them (a mid-run question, V11; cancel, V3). LangGraph, its checkpointer, the
graph nodes and the prompts sit behind it, and ruff `TID251` lets only that package import LangGraph,
exactly as only `glean/llm.py` may import LangChain. Ripping LangGraph out for a hand-written loop
would change this package and nothing else.

**Liveness is the session's own lease, not a second orchestrator.** The queue's visibility timeout is
150 s: the worker's 120 s timeout, plus up to 10 s of Lambda init before the handler runs, plus margin —
the pairing AWS requires of an SQS event source (cfn-lint E3505) and enough for a message to stay
invisible past any run it can deliver. What makes a crashed run recoverable is written on the session
item instead: the attempt that starts a run takes an owner token and a lease, taken **once**, at claim,
never extended, and **anchored to its own invocation deadline** — `now + remaining time + 2 s`, where
the remaining time comes from the Lambda context. A constant measured from claim time could outlive the
visibility, because the claim happens after init and the first reads while the queue's clock started at
the receive; the invocation's deadline cannot, because a Lambda is certainly gone then.

Every later write is conditioned on the owner token. A delivery may claim a session that is `queued`, or
`running` with a lapsed lease, and a takeover **resumes from the LangGraph checkpoint** rather than
starting again — or publishes the plan the finished checkpoint already holds. A delivery that finds a
**live** owner does not drop: it **fails**, so the message is not acknowledged and comes back after the
visibility timeout. Acknowledging it would delete the logical message — the only trigger that recovers
the run — while the other copy is still working, and if that copy then died nothing would be left to
pick the session up. Acknowledging is reserved for a terminal session (nothing left to do) and for runs
this invocation completed. The queue therefore allows three receives rather than two: one may be spent
failing a live duplicate, and two genuine attempts still fail a session before its message is
dead-lettered.

The dead-letter queue is a retry loop, not a bin. Its handler marks a session `failed / worker_failed`
only when it is nonterminal *and* its lease has lapsed; when a live run still owns it, the handler
**raises**, so the dead letter is kept and retried on the dead-letter queue's own 60 s visibility
timeout. Acknowledging there would delete the last trigger that can fail or resume the session if that
run then died. It acknowledges only what is finished: the session missing (expired), already terminal,
or newly failed. So a session sits at most one dead-letter retry (about a minute) past its lease
lapsing — about 3 minutes after a crash, or immediately after the owner's own 120 s timeout — which is
still inside the app's five-minute cap. A crashed run comes back within about 2.5 minutes.

One run also has a budget: 90 s and 8 tool calls (§6.2). It is checked before every graph step, the
one blocking call (the model) gets only what is left of it, and spending it -- like a model or tool
error -- ends the session with the degraded plan: the scorer's best week with template reasons. Only a
budget spent before the scorer has run, in `prepare`, ends `failed / model_error`.

**Considered options.**

- **Step Functions around the run.** Rejected: a second orchestrator overlapping LangGraph, with its
  own state, retries and visibility into a graph that already checkpoints every step. The lease on the
  session gives the same guarantee — a run is retried while it is unrecoverable and dead-lettered when
  it is not — for one resource and no new execution model.
- **A 60 s visibility timeout renewed by the worker every 20 s.** Rejected by the platform: an SQS
  event source requires the visibility timeout to be at least the function timeout, so the pair was
  undeployable. Renewal could not fix that, and with the queue outliving the function it earns nothing.
- **A sliding lease, refreshed as the graph moves.** Rejected: a refreshed lease (claim + 45 s prepare
  + 120 s) outlives the visibility, so the redelivered message would find a live owner, be
  acknowledged, and leave the session `running` for ever with nothing left to recover it.
- **A fixed lease measured from claim time, and a plain "nothing to do" for a live duplicate.**
  Rejected twice over: the claim happens seconds into the invocation (init, settings, the first reads),
  so a constant can expire after the message has already reappeared; and returning success for
  nonterminal work acknowledges (deletes) the message the live run depends on. The lease follows the
  invocation's deadline, and a live duplicate fails its delivery instead.
- **A visibility timeout below the function timeout, with the suppression of E3505.** Rejected: the
  suppression hid an integration constraint, and the deploy would fail on the event-source mapping.
- **Push (WebSocket/AppSync) instead of polling.** Deferred: polling every second costs one read and
  needs no connection state, and the app already polls for its catalogue sync.

**Consequences.**

- **Capacity.** `agent_sessions` at 2/2 and `agent_checkpoints` at 3/3 join the catalogue's 10/10. F1
  (#162) adds the recipe store at 5/5, making the account 20/20 against the free tier's 25/25
  (ADR 0001); `tests/infra/test_template_free_tier.py` sums them and reserves F1's share.
- **Every queue consumer acknowledges only work that is finished.** A busy delivery, on the source
  queue or the dead-letter queue, fails instead of returning: in SQS a successful return *is* the
  delete. That is why the dead-letter queue has its own short visibility timeout and why its handler
  distinguishes "still live" from "nothing to do".
- **The queue's timeout, the function's timeout, init and the lease move together.** The visibility
  timeout must stay above the worker's timeout plus the longest init (E3505 is enforced, not
  suppressed), and the longest lease any attempt can take must end before it. A lease taken at the
  very start of a full invocation ends 2 s after the function timeout; a late claim ends earlier,
  because it is the remaining time that is measured. The numbers live in `sessions/store.py` and the
  template test checks `template.yaml` against them.
- **The item's size is bounded at both ends.** Inputs are stored gzipped and `create` refuses a request
  whose item would not leave room for the progress lines and the plan (422), so a large but valid
  request is refused rather than failing at the first write. The plan is measured too: 64 KB is
  reserved for it (V3 adds an alternative per meal and the planned meals' reasons), and `complete`
  refuses a result that would overflow the item, which fails the session `model_error` with the reason
  logged rather than raising into SQS. Nothing in the schemas bounds a model's prose, so a reserve
  alone would be an assumption.
- **The checkpointer is not an API.** Nothing outside `glean.agent` reads `agent_checkpoints`, and
  the table is the agent's to replace.
- **The synchronous endpoint stays** until the phone runs a build that uses sessions, then goes in a
  follow-up PR. Both paths call `meal_plan.pipeline`, so they cannot drift while both exist.
- **A degraded plan is still a plan.** `SessionsDegraded` counts V7's fallback (the scorer's best week
  with template reasons), which the household cannot tell apart; with started, completed, failed,
  cancelled, wall time and the per-session tool calls, invalid answers and drift, it is how a
  regression in the agent shows up at all.
