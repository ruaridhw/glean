"""The planning agent, as one deep module. LangGraph, the checkpointer and the prompts stay inside.

Call `start(session)` for every queue delivery: a new session runs `prepare -> plan <-> act -> finalise` to a
terminal status in the session store, or parks it on the agent's one question as `waiting_for_user` (V11); a
parked one with its answer stored continues from its checkpoint; and a finished one with a swap queued resumes
from its checkpoint with it, replacing one meal. Call `cancel(session_id)` and the run in flight stops writing at
its next step. Nothing outside `glean.agent` imports LangGraph (ruff `TID251`), so replacing the graph with a
hand-written loop would change this package and nothing else.

Call `resume(session_id, message)` with a household message: it stores the message on the item and re-enqueues
the session, and the delivery's `start` finds it there. V10's swap is one message; V11's answer and skip are the
others, resuming a run parked on its question.
"""

from glean.agent.deps import AgentDeps, build_deps
from glean.agent.runtime import MessageNotSent, cancel, resume, start

__all__ = ["AgentDeps", "MessageNotSent", "build_deps", "cancel", "resume", "start"]
