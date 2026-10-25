"""The planning agent, as one deep module. LangGraph, the checkpointer and the prompts stay inside.

Call `start(session)` with a claimed session and it runs `prepare -> plan <-> act -> finalise` to a
terminal status in the session store; call `cancel(session_id)` and the run in flight stops writing at its next
step. Nothing outside `glean.agent` imports LangGraph (ruff `TID251`), so replacing the graph with a
hand-written loop would change this package and nothing else.

`resume` is the interface's other call (spec §6.2). It arrives with the route that uses it -- a
mid-run question is V11 -- rather than as a stub nobody calls.
"""

from glean.agent.deps import AgentDeps, build_deps
from glean.agent.runtime import cancel, start

__all__ = ["AgentDeps", "build_deps", "cancel", "start"]
