#!/usr/bin/env python3
"""Workspace framework library — ranked framework choices with user-fillable
parameters for the Surveyor workspace builder.

Two pure functions with deliberately separate inputs:
  rank_frameworks(identifier_cards)  -> WHAT framework (identifier cards only)
  prefill_params(framework_id, signals) -> HOW it's configured (signals only)

Do not merge these. Identifiers rank; signals prefill. Neither function reads
the other's input, and neither mutates its arguments.
"""

# Confidence word -> weight, mirroring identifiers.py's evidence wording.
_CONFIDENCE_WEIGHT = {"clear": 1.0, "emerging": 0.66, "early": 0.33}

# Declaration order is the final tiebreak in rank_frameworks — keep this order
# deliberate, same pattern as identifiers.py's use of types.CRITERIA.
FRAMEWORKS = {
    "node_graph": {
        "name": "Node graph canvas",
        "serves": {
            "visual_systems_thinking": 1.0,
            "workflow_decomposition": 0.7,
        },
        "params": {
            "node_source": {
                "type": "text",
                "ask": "What should each node represent?",
                "default": None,
            },
            "edge_meaning": {
                "type": "enum",
                "ask": "What does a connection between nodes mean?",
                "options": ["sequence", "dependency", "data_flow"],
                "default": "sequence",
            },
            "dimensions": {
                "type": "enum",
                "ask": "Flat or depth view?",
                "options": ["2d", "3d"],
                "default": "2d",
            },
        },
    },
    "code_ide": {
        "name": "Code workspace",
        "serves": {
            "visual_systems_thinking": 0.6,
            "domain_specificity": 0.8,
        },
        "params": {
            "language": {
                "type": "text",
                "ask": "Which language do you work in most?",
                "default": None,
            },
            "repo": {
                "type": "text",
                "ask": "Which repository or project should this open to?",
                "default": None,
            },
        },
    },
    "plot_dashboard": {
        "name": "Plot dashboard",
        "serves": {
            "verification_instinct": 0.9,
            "visual_systems_thinking": 0.5,
        },
        "params": {
            "x_axis": {
                "type": "text",
                "ask": "What goes on the horizontal axis?",
                "default": None,
            },
            "y_axis": {
                "type": "text",
                "ask": "What goes on the vertical axis?",
                "default": None,
            },
            "plot_type": {
                "type": "enum",
                "ask": "Which plot style fits the data?",
                "options": ["line", "scatter", "bar"],
                "default": "line",
            },
        },
    },
    "chat_workspace": {
        "name": "Guided chat workspace",
        "serves": {
            "intent_clarity": 0.9,
            "constraint_setting": 0.8,
            "delegation_readiness": 0.7,
            "human_checkpoint_judgment": 0.7,
            "gap_detection": 0.6,
            "risk_boundary_awareness": 0.6,
        },
        "params": {
            "opening_context": {
                "type": "text",
                "ask": "What should it know before you start?",
                "default": None,
            },
            "reply_length": {
                "type": "enum",
                "ask": "How long should replies run?",
                "options": ["brief", "standard", "thorough"],
                "default": "standard",
            },
        },
    },
}


def rank_frameworks(identifier_cards):
    """Rank frameworks against identifier cards. Pure function.

    Input: list of card dicts from identifiers.build() — keys 'criterion' and
    'confidence' are read; everything else is ignored. Cards arrive pre-sorted
    best-first; that ordering is the secondary sort key.

    Output: [{"framework_id", "score", "matched_criterion"}, ...], best first.
    Zero-score frameworks are dropped. Empty input returns [].

    Sort: score desc, then index of the card that produced the winning score
    asc, then FRAMEWORKS declaration order asc.
    """
    if not identifier_cards:
        return []

    decl_order = {fid: i for i, fid in enumerate(FRAMEWORKS)}
    best = {}  # framework_id -> (score, card_index, matched_criterion)

    for card_index, card in enumerate(identifier_cards):
        criterion = card.get("criterion")
        weight = _CONFIDENCE_WEIGHT.get(card.get("confidence"), 0.0)
        if not criterion or weight == 0.0:
            continue
        for fid, fw in FRAMEWORKS.items():
            score = fw["serves"].get(criterion, 0.0) * weight
            if score <= 0.0:
                continue
            current = best.get(fid)
            # Keep the winning card: higher score wins; equal score keeps the
            # earlier card index (cards are pre-sorted best-first).
            if current is None or score > current[0]:
                best[fid] = (score, card_index, criterion)

    ranked = sorted(
        best.items(),
        key=lambda kv: (-kv[1][0], kv[1][1], decl_order[kv[0]]),
    )
    return [
        {"framework_id": fid, "score": score, "matched_criterion": criterion}
        for fid, (score, _idx, criterion) in ranked
    ]


def prefill_params(framework_id, signals):
    """Prefill a framework's params from profile signals. Pure function.

    Input: a framework id from FRAMEWORKS and the profile's signals dict.
    Output: {param_id: value}, starting from each param's default.
    Unknown framework ids return {}.
    """
    fw = FRAMEWORKS.get(framework_id)
    if not fw:
        return {}
    signals = signals or {}

    out = {pid: p.get("default") for pid, p in fw["params"].items()}

    # Detailed-density readers get the denser plot style.
    if signals.get("interface_density") == "detailed" and "plot_type" in out:
        out["plot_type"] = "scatter"

    return out
