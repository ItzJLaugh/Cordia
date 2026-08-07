#!/usr/bin/env python3
"""CordiaAIE (course aie1) -> 6S registry.

Maps the 12 scored blocks of "Saying What You Mean" onto the 6S matrix so the
shadow scorer can produce a real dimension/tier matrix from actual exam
submissions, instead of the abstract S-items which no exam produces.

TIER
    aie1 belongs to the CordiaAIE tier, which curriculum-tiers.js describes as
    the Article 4 baseline — "state what they want, recognize when they didn't
    get it". That is the foundation tier. CordiaCAIE ("specify a workflow well
    enough that someone else could verify it") is design, and CordiaCAAIE is
    configuration. So every aie1 block lands in the foundation column, and the
    design/configuration columns stay null until those tiers are wired up.

DIMENSIONS
    Derived from each block's own `why` field in cordaie_rubrics.json:

      m0e0 vague problem -> concrete instruction ............ Source
      m0e1 blame the missing definition, not the agent ...... Source
      m0e2 when the agent may decide vs when a human must ... Safety
      m1e0 define success in checkable terms ................ Success
      m1e1 explicit verification targets .................... Success
      m1e2 tie success criteria to a preventing gate ........ Success
      m2e0 exact checkpoint trigger ......................... Steering
      m2e1 checkpoint only where a mistake is expensive ..... Steering
      m2e2 stop the chain on external consequences .......... Switch
      m3e0 name exact deltas and recurrence rules ........... Sharpen
      m3e1 update the definition, not one output ............ Sharpen
      m3e2 identify the layer that caused the wrong output .. Switch

    That fills the entire foundation row: all six dimensions covered.

STATUS — DIMENSION MAP SIGNED OFF; ANCHORS STILL DRAFT
    The two arguable assignments were confirmed by the curriculum owner on
    2026-08-07, both keeping their original dimension:

      m0e2  Safety  (not Switch) — read as setting the permission boundary up
            front, who may decide what, rather than as the handoff itself. This
            is also the only block assigned to Safety, so moving it would have
            left the dimension unmeasured and broken full foundation-row cover.
      m3e2  Switch  (not Sharpen) — read as routing to the layer responsible,
            which is escalation work, rather than as the revision that follows.

    That settles the dimension map. It does NOT make the scoring validated —
    the two are independent, and only the first one is done.

    The anchors below are a FIRST DRAFT written from the `why` fields, not
    validated exemplars. The fix instructions call for 5-8 anchors per item
    with authorship split from whoever wrote the structural check — neither
    condition is met yet. This is why the version string says unvalidated and
    why nothing here is shown to a learner.

    Structural checks are deliberately broad alternations rather than narrow
    keyword lists. The offline stability test showed narrow keyword regex is
    the fragile half (swing 47.9 vs 2.4 for char TF-IDF), so these lean on
    concept classes — negation, quantities, named actors, conditionals — and
    carry only 25% of the blend.
"""

from __future__ import annotations

from .rubric import Registry

COURSE_ID = "aie1"
TIER = "foundation"

AIE1_VERSION = "cordaie-aie1-6s-heuristic-v1-unvalidated"

BLOCK_DIMENSION = {
    "m0e0": "Source",
    "m0e1": "Source",
    "m0e2": "Safety",
    "m1e0": "Success",
    "m1e1": "Success",
    "m1e2": "Success",
    "m2e0": "Steering",
    "m2e1": "Steering",
    "m2e2": "Switch",
    "m3e0": "Sharpen",
    "m3e1": "Sharpen",
    "m3e2": "Switch",
}

ITEM_MAP = {block: (dim, TIER) for block, dim in BLOCK_DIMENSION.items()}

# Documented failure patterns per block: what a weak answer sounds like.
FAILURE_ANCHORS = {
    "m0e0": [
        "Help me write something for this.",
        "Make it better and more professional.",
        "Use AI to improve the process.",
        "Just summarize the information for the team.",
    ],
    "m0e1": [
        "The AI got it wrong and made things up.",
        "The model is not smart enough for this task.",
        "It hallucinated, so the tool is unreliable.",
        "The output was bad because the AI misunderstood.",
    ],
    "m0e2": [
        "Use your best judgment on anything unclear.",
        "Escalate if something seems important.",
        "Check with someone if you are unsure.",
        "The agent should ask a human when needed.",
    ],
    "m1e0": [
        "It should be accurate and high quality.",
        "Success means the client is happy with it.",
        "The output should be good and useful.",
        "Make sure it is correct.",
    ],
    "m1e1": [
        "This option is clearer and sounds better.",
        "I picked this one because it is more detailed.",
        "The second one is more professional.",
        "This instruction is easier to understand.",
    ],
    "m1e2": [
        "I would review the output before sending it.",
        "Check the result and fix anything wrong.",
        "Read it over to make sure it is fine.",
        "Proofread before it goes out.",
    ],
    "m2e0": [
        "Check in with me regularly during the task.",
        "Report progress as the work continues.",
        "Let me know how it is going.",
        "Provide updates at reasonable intervals.",
    ],
    "m2e1": [
        "More checkpoints are safer, so add them everywhere.",
        "Review every step to be careful.",
        "It is better to check often than to miss something.",
        "Add a checkpoint after each action.",
    ],
    "m2e2": [
        "Continue unless there is an obvious problem.",
        "Keep going and flag issues at the end.",
        "Finish the task and report anything unusual.",
        "Proceed and mention any concerns afterwards.",
    ],
    "m3e0": [
        "Make it shorter and clearer this time.",
        "Try again with a better tone.",
        "This is not quite right, please redo it.",
        "Improve the draft and send it back.",
    ],
    "m3e1": [
        "Fix this sentence and it will be fine.",
        "Just correct the error in this version.",
        "Change that one line and resend.",
        "Edit the mistake and move on.",
    ],
    "m3e2": [
        "The output was wrong so the prompt needs work.",
        "Something went wrong somewhere in the process.",
        "The result is incorrect, try a different approach.",
        "It failed, so we should start over.",
    ],
}

# Concept classes, reused across blocks. Broad on purpose.
_QUANTITY = r"\b\d+\b|\b(one|two|three|four|five|ten|twenty|thirty|hour|hours|day|days|week|weeks|minute|minutes|percent|%)\b"
_NEGATION = r"\b(not|never|no|without|unless|except|cannot|must not|do not|don't)\b"
_CONDITION = r"\b(if|when|whenever|once|before|after|until|in the event)\b"
_CAUSAL = r"\b(because|so that|in order to|which means|therefore|that is why|since)\b"
_ACTOR = r"\b(owner|manager|partner|client|reviewer|analyst|human|approver|lead)\b|[A-Z][a-z]+\s[A-Z][a-z]+"
_ARTIFACT = r"\b(brief|report|summary|dashboard|email|memo|draft|spec|specification|table|list|document)\b"
_VERIFY = r"\b(verify|check|confirm|validate|test|compare|match|cross-check|reconcile)\b"
_DEFINITION = r"\b(definition|criteria|criterion|standard|rule|instruction|spec|specification|requirement)\b"

STRUCTURAL_CHECKS = {
    "m0e0": [_ARTIFACT, _CAUSAL, _QUANTITY],
    "m0e1": [_DEFINITION, _NEGATION, _CAUSAL],
    "m0e2": [_CONDITION, _ACTOR, _NEGATION],
    "m1e0": [_VERIFY, _CONDITION, _QUANTITY],
    "m1e1": [_VERIFY, _CAUSAL, _DEFINITION],
    "m1e2": [_VERIFY, _CONDITION, _NEGATION],
    "m2e0": [_CONDITION, _QUANTITY, _ACTOR],
    "m2e1": [_CONDITION, _CAUSAL, _NEGATION],
    "m2e2": [_NEGATION, _CONDITION, _ACTOR],
    "m3e0": [_QUANTITY, _DEFINITION, _CONDITION],
    "m3e1": [_DEFINITION, _NEGATION, _CAUSAL],
    "m3e2": [_CAUSAL, _DEFINITION, _CONDITION],
}

AIE1_REGISTRY = Registry(
    name="cordaie-aie1",
    version=AIE1_VERSION,
    item_map=ITEM_MAP,
    anchors=FAILURE_ANCHORS,
    checks=STRUCTURAL_CHECKS,
    weights={},                       # uniform: no block has a proven-stable check yet
    case_sensitive_items=frozenset(),  # _ACTOR has a capitalised alternative but
                                       # also matches lowercase role nouns
)


def latest_by_block(response_rows: list[dict]) -> dict[str, str]:
    """Most recent answer per block, mirroring cordaie_scoring._latest_by_block.

    Kept behaviourally identical so the shadow matrix is computed from exactly
    the same answers the learner-visible score used.
    """
    latest: dict[str, str] = {}
    latest_ts: dict[str, float] = {}
    for r in response_rows:
        block = r.get("block")
        ts = r.get("ts", 0) or 0
        if block is not None and ts >= latest_ts.get(block, -1):
            latest_ts[block] = ts
            latest[block] = r.get("value", "")
    return latest


def registry_for(track: str | None) -> Registry | None:
    """Which registry scores this track, or None if the track is not mapped.

    Returning None is the honest answer for an unmapped track — better an
    absent score than a matrix built from items that do not apply.
    """
    if track and str(track).strip().lower() in (COURSE_ID, "aie1", "aie-1", "cordaie", "aie"):
        return AIE1_REGISTRY
    return None
