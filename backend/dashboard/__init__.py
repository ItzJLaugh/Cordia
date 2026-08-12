"""Cordia Agent Dashboard — backend for the visual canvas surface.

A new surface beside the existing site, consuming the same interface-definition
data model as Surveyor's builder: the survey profile shapes a starting layout,
the person refines it by talking to the agent and by direct manipulation on a
node/edge canvas, then runs it and reports whether it helped.

Same ground rules as the surveyor package it sits beside:

  * Soft-imported by the training backend — a bug here answers 503 on
    /dashboard/* routes and must never stop auth or the exam from booting.
  * The model (when wired) powers only builder reasoning. Certification
    scoring and the deterministic profile scoring stay model-free.
  * Nothing negative is ever surfaced to the user.
"""

from . import types

__all__ = ["types"]
