"""Cordia Surveyor — conversational intake, profile, and workspace adaptation.

Intent cannot be measured, but it can be surveyed. Surveyor talks to a person,
turns what they say into an inspectable profile, and uses that profile to shape
an agentic workspace they then build and run.

Two rules hold the design together:

  * The profile's numbers are internal. They are data for the next scoring
    layer, never a grade, and they never touch the certification score.
  * What the person sees back is three positive identifiers telling them how to
    use AI. Nothing negative is ever surfaced.

No machine learning is implemented here, and none should be added. Question
choice is rules; extraction is one LLM call whose output is validated against
allow-lists; scoring is a lookup table. If any of it starts to need a model to
work, the right move is to delete the feature, not to grow one.
"""

from . import (adaptation, alidora, artifacts, capability_gateway, extractor, fde_registry, fde_routing, freeform, github_connector, hitl_policy, identifiers, intent_misses, llm, mock, permissions, pipeline, skills,
               prompts, question_strategy, recommendation, runtime_config, scenarios, scorer, store,
               types, vault, workspace_state)

__all__ = ["adaptation", "alidora", "artifacts", "capability_gateway", "extractor", "fde_registry", "fde_routing", "freeform", "github_connector", "hitl_policy", "identifiers", "intent_misses", "llm", "mock", "permissions", "skills",
           "pipeline", "prompts", "question_strategy", "recommendation", "runtime_config", "scenarios",
           "scorer", "store", "types", "vault", "workspace_state"]
