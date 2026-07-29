"""Shared CordiaAIE example answers used by the offline plotting tools.

Illustrative exemplars written to exercise the scorer, NOT validated
reference answers. Real exemplars have to come from the curriculum owner.
"""

STRONG = {
    "m0e0": "Produce a one-page partner briefing for the Q3 review, because the partners decide budget from it, within 2 pages.",
    "m0e1": "The instruction never defined which ledger counts as the source, so the definition is missing, not the model.",
    "m0e2": "If the request touches client data the agent must not proceed; the reviewer approves before anything is sent.",
    "m1e0": "Success means every figure can be verified against the source ledger; if a figure cannot be checked the draft is not done.",
    "m1e1": "I chose the second because it names the verification target and says what happens when it fails.",
    "m1e2": "Before sending, confirm each number against the ledger; if any cannot be matched, do not send.",
    "m2e0": "When the total exceeds 10,000 the manager approves before the next step.",
    "m2e1": "The checkpoint belongs before the transfer because that step cannot be reversed afterwards.",
    "m2e2": "Do not send anything externally; stop and escalate to the owner first.",
    "m3e0": "Shorten section 2 to 3 bullets and apply that rule to every future draft because partners skim the opening.",
    "m3e1": "Update the definition so it excludes draft ledgers, rather than correcting this one output.",
    "m3e2": "The wrong figure came from the retrieval step, not the drafting step, because the source was stale.",
}
