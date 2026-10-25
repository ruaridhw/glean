"""The planning agent, as one deep module. LangGraph, the checkpointer and the prompts stay inside.

Call `start(session)` for every queue delivery: a new session runs `prepare -> plan <-> act -> finalise` to a
terminal status in the session store, and a finished one with a swap queued resumes from its checkpoint with
it, replacing one meal. Call `cancel(session_id)` and the run in flight stops writing at its next
step. Nothing outside `glean.agent` imports LangGraph (ruff `TID251`), so replacing the graph with a
hand-written loop would change this package and nothing else.

Resuming with a household message (spec §6.2's `resume`) is a delivery like any other: the route stores the
message on the item and re-enqueues the session, and `start` finds it there. V10's swap is the first message;
V11's answer and skip resume a run parked on its question the same way.
"""

from glean.agent.deps import AgentDeps, build_deps
from glean.agent.runtime import cancel, start

__all__ = ["AgentDeps", "build_deps", "cancel", "start"]
