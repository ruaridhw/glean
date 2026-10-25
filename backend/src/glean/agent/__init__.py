"""The planning agent, as one deep module. LangGraph, the checkpointer and the prompts stay inside.

Call `deliver(session)` for one queue delivery: a new session runs `prepare -> plan <-> act -> finalise` to a
terminal status in the session store (`start`), and a finished one with a swap queued is resumed with it
(`resume`), replacing one meal. Call `cancel(session_id)` and the run in flight stops writing at its next
step. Nothing outside `glean.agent` imports LangGraph (ruff `TID251`), so replacing the graph with a
hand-written loop would change this package and nothing else.

`resume(session, message)` is the interface's other call (spec §6.2). V10's swap is its first message; V11's
answer and skip resume a run parked on its question the same way.
"""

from glean.agent.deps import AgentDeps, build_deps
from glean.agent.runtime import cancel, deliver, resume, start

__all__ = ["AgentDeps", "build_deps", "cancel", "deliver", "resume", "start"]
