#!/usr/bin/env python3
"""Custom coding model behind a Cordia agentic interface.

NOT IMPLEMENTED IN MVP. EXTENSION POINT ONLY.

This file exists so the future build starts from measured facts rather than
assumptions. Two were checked on this host and both constrain the design.

1. HARDWARE — a local model is not on the table here
----------------------------------------------------
This VPS has 2 CPU cores, ~7 GB RAM (~5 GB free), no GPU, and the training
backend alone already holds several hundred MB resident. A 27B-parameter model
needs roughly 16 GB even at 4-bit quantization, and would run at a fraction of a
token per second on 2 cores with no GPU regardless.

So a custom coding model must be *hosted*, reached over HTTP behind the same
seam as call_llm() in training_backend.py. Swapping the endpoint is a small
change; running the weights here is not a smaller one, it is an impossible one.
Do not plan around "we'll self-host it later" without new hardware.

2. ALIGNMENT — pick a model that matches what Cordia sells
----------------------------------------------------------
A safety-ablated model was floated for this slot (a "Heretic"-method Qwen
derivative whose published card reports refusals dropped from 99/100 to 4/100,
marketed as uncensored / all use cases).

That is a poor fit here, and the reason is product, not squeamishness. Cordia's
entire premise is teaching people to operate AI with stated boundaries, risk
awareness and human checkpoints before anything goes out. Shipping a model
chosen for having had its boundaries removed contradicts the thing being sold,
and it is the kind of detail that surfaces in exactly the enterprise review
where Cordia most wants to look credible.

A mainstream open-weights coding model gets the same capability without the
positioning problem. Recommend evaluating those first.

3. FINE-TUNING — not yet, on the evidence
------------------------------------------
Cordia's corpus is a few hundred responses from ~13 learners. That is far short
of what a useful fine-tune needs. Prompting and context are the cheaper win
until there is materially more real usage data.

Interface, when it is built:

    def complete(prompt: str, *, context: dict, max_tokens: int = 1024) -> str
    def available() -> bool
"""

from __future__ import annotations


def available() -> bool:
    """Whether a custom coding model is configured. Always False in the MVP."""
    return False


def complete(prompt, *, context=None, max_tokens=1024):
    raise NotImplementedError(
        "Custom coding model is an extension point, not implemented in the MVP. "
        "See the module docstring for the hardware and model-choice constraints.")
