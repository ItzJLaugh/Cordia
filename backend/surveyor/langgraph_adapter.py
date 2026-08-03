#!/usr/bin/env python3
"""Convert a Cordia interface definition into a LangGraph graph.

NOT IMPLEMENTED IN MVP. EXTENSION POINT ONLY.

The MVP runs an interface as a single prompted call built from the definition
(see pipeline/runtime). That is enough to prove the shape is useful and cheap to
throw away if it isn't.

The definition is already graph-shaped on purpose: `agents` are nodes,
`workflow.steps` are edges in order, and `requiresApproval` marks an interrupt
point. When this is built, steps map to nodes, the ordered list becomes the
edges, and requiresApproval becomes a LangGraph interrupt handled by hitl_policy.

LangChain is deliberately NOT a dependency yet — it is not installed in the venv,
and adding a large dependency tree to serve one uninstantiated abstraction would
cost startup time on a 2-core host for no present benefit.

    def to_graph(definition: dict): ...
"""

from __future__ import annotations


def available() -> bool:
    return False


def to_graph(definition):
    raise NotImplementedError(
        "LangGraph adapter is an extension point, not implemented in the MVP.")
