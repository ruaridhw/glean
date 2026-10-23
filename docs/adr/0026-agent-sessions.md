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
130 s and the worker's timeout is 120 s, the pairing AWS requires of an SQS event source (cfn-lint
E3505) — a message therefore stays invisible for at least as long as any run it can deliver. What
makes a crashed run recoverable is written on the session item instead: the attempt that starts a run
takes an owner token and a lease taken **once**, at claim, never extended — 125 s, which is the worker's
120 s timeout plus a 5 s margin, and therefore shorter than the 130 s visibility. Every later write is
conditioned on that token. A delivery may claim a session that is `queued`, or `running` with a lapsed
lease; a live duplicate is told it is owned elsewhere and drops; a redelivery after a crash takes over
and **resumes from the LangGraph checkpoint** rather than starting again. So a crashed run comes back
within about two minutes and still lands inside the app's five-minute cap, and a worker that was taken
over can no longer write the outcome. After two failed attempts the message reaches the dead-letter
queue, whose handler marks the session `failed / worker_failed`, with no owner needed.

One run also has a budget: 90 s (§6.2). It is checked before every graph step, the one blocking call
(the model) gets only what is left of it, and spending it ends the session `failed / model_error`
until V6's scorer exists to supply the degraded plan.

**Considered options.**

- **Step Functions around the run.** Rejected: a second orchestrator overlapping LangGraph, with its
  own state, retries and visibility into a graph that already checkpoints every step. The lease on the
  session gives the same guarantee — a run is retried while it is unrecoverable and dead-lettered when
  it is not — for one resource and no new execution model.
- **A 60 s visibility timeout renewed by the worker every 20 s.** Rejected by the platform: an SQS
  event source requires the visibility timeout to be at least the function timeout, so the pair was
  undeployable. Renewal could not fix that, and with the queue outliving the function it earns nothing.
- **A sliding lease, refreshed as the graph moves.** Rejected: a refreshed lease (claim + 45 s prepare
  + 120 s) outlives the 130 s visibility, so the redelivered message would find a live owner, be
  acknowledged, and leave the session `running` for ever with nothing left to recover it. A fixed
  lease cannot: 125 s after the claim the attempt is provably gone (a Lambda cannot outlive its
  timeout), while a duplicate copy delivered alongside a live run still finds it live and is dropped.
- **A visibility timeout below the function timeout, with the suppression of E3505.** Rejected: the
  suppression hid an integration constraint, and the deploy would fail on the event-source mapping.
- **Push (WebSocket/AppSync) instead of polling.** Deferred: polling every second costs one read and
  needs no connection state, and the app already polls for its catalogue sync.

**Consequences.**

- **Capacity.** `agent_sessions` at 2/2 and `agent_checkpoints` at 3/3 join the catalogue's 10/10. F1
  (#162) adds the recipe store at 5/5, making the account 20/20 against the free tier's 25/25
  (ADR 0001); `tests/infra/test_template_free_tier.py` sums them and reserves F1's share.
- **The queue's timeout, the function's timeout and the lease move together.** The visibility timeout
  must stay above the worker's timeout (E3505 is enforced, not suppressed), and the lease must sit
  between them: above the function timeout so a live run is never taken over inside its own
  invocation, below the visibility timeout so every redelivery finds it lapsed. The three numbers live
  in `sessions/store.py` and the template test checks `template.yaml` against them.
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
- **No degraded plan in V1.** `SessionsDegraded` is reserved for V7's fallback (the scorer's best plan
  with template reasons); the CloudWatch metrics emitted today are started, completed, failed and
  wall time.
