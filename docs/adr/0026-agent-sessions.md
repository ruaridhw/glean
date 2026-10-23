---
status: accepted
date: 2026-10-22
---

# Agent sessions are the backend's one transient per-user state, and the queue lease is their liveness

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

**Liveness is the SQS lease, not a second orchestrator.** The queue's visibility timeout is 60 s and
the worker renews it every 20 s while the graph runs. If the worker crashes or times out the
renewals stop, the message reappears within a minute and the run is retried from its checkpoint. Only
a conditional `queued → running` write starts a run, so a duplicate delivery finds the session
running and drops. After two failed attempts the message reaches the dead-letter queue, whose handler
marks the session `failed / worker_failed`. Every session therefore reaches `done` or `failed`
through infrastructure.

**Considered options.**

- **Step Functions around the run.** Rejected: a second orchestrator overlapping LangGraph, with its
  own state, retries and visibility into a graph that already checkpoints every step. The queue's
  lease gives the same guarantee — a run is retried while it is unrecoverable and dead-lettered when
  it is not — for one resource and no new execution model.
- **A heartbeated DynamoDB `lease_until` field, with a sweeper.** Rejected: two sources of truth for
  "is this run alive" (the message's visibility and the item's lease) and a sweeper to write.
- **Lambda's own retry with a visibility timeout above the function's timeout.** Rejected by the
  design: then a crashed run blocks its session for the full function timeout, and a redelivery can
  never arrive while a run is still making progress.
- **Push (WebSocket/AppSync) instead of polling.** Deferred: polling every second costs one read and
  needs no connection state, and the app already polls for its catalogue sync.

**Consequences.**

- **Capacity.** `agent_sessions` at 2/2 and `agent_checkpoints` at 3/3 join the catalogue's 10/10. F1
  (#162) adds the recipe store at 5/5, making the account 20/20 against the free tier's 25/25
  (ADR 0001); `tests/infra/test_template_free_tier.py` sums them and reserves F1's share.
- **Deleting or merging the queue is not a tuning change.** The 60 s/20 s pair is what makes a
  duplicate delivery routine and a stuck session impossible, so the template suppresses cfn-lint
  `E3505` (which wants the visibility timeout to exceed the function timeout) deliberately.
- **The checkpointer is not an API.** Nothing outside `glean.agent` reads `agent_checkpoints`, and
  the table is the agent's to replace.
- **The synchronous endpoint stays** until the phone runs a build that uses sessions, then goes in a
  follow-up PR. Both paths call `meal_plan.pipeline`, so they cannot drift while both exist.
- **No degraded plan in V1.** `SessionsDegraded` is reserved for V7's fallback (the scorer's best plan
  with template reasons); the CloudWatch metrics emitted today are started, completed, failed and
  wall time.
