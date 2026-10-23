"""The planning agent, as one deep module. LangGraph, the checkpointer and the prompts stay inside.

Call `start(session)` with a claimed session and it runs `prepare -> plan -> finalise` to a terminal
status in the session store. Nothing outside `glean.agent` imports LangGraph (ruff `TID251`), so
replacing the graph with a hand-written loop would change this package and nothing else.

`resume` and `cancel` are the interface's other two calls (spec §6.2). They arrive with the routes
that use them -- a mid-run question is V11, cancel is V3 -- rather than as stubs nobody calls.
"""

from glean.agent.deps import AgentDeps, build_deps
from glean.agent.runtime import start

__all__ = ["AgentDeps", "build_deps", "start"]
