#!/usr/bin/env python3
"""One Surveyor turn, end to end.

Kept out of the HTTP handler so the sequence stays readable and testable:

    store the message
    -> extract observations   (LLM, may fail; failure is survivable)
    -> merge into the profile (validated, allow-listed)
    -> rescore the criteria   (rules)
    -> rebuild identifiers    (top three, positive only)
    -> choose the next question (rules)
    -> store the reply

The only step that can fail unpredictably is extraction, and it is explicitly
allowed to: on failure we keep the previous profile, log it, and carry on with
the next question. A person mid-conversation must never lose what they have
already told us because a model returned bad JSON.
"""

from __future__ import annotations

from . import (adaptation, extractor, identifiers, prompts,
               question_strategy as qs, scorer, store, types)

MAX_ANSWER = 4000


def load_profile(email) -> dict:
    stored = store.get_profile(email)
    if not stored:
        return types.empty_profile()
    p = types.empty_profile()
    p.update({k: v for k, v in stored.items() if v is not None})
    return p


def public_profile(email, profile=None) -> dict:
    """What the browser is allowed to see: the three identifiers, progress, and
    the next action. No scores, no evidence, no criteria names."""
    p = profile or load_profile(email)
    return {
        "identifiers": p.get("identifiers") or [],
        "percent_complete": int(round(100 * float(p.get("confidence") or 0.0))),
        "questions_answered": int(p.get("questions_answered") or 0),
        "next_action": identifiers.next_best_action(p),
        "personalization": adaptation.effective_mode(p),
        "simple_mode_forced": bool(p.get("simple_mode_forced")),
    }


def start(email) -> dict:
    """Open (or resume) the conversation and return the transcript."""
    cid = store.open_conversation(email)
    history = store.messages(cid)
    if not history:
        store.add_message(cid, "assistant", qs.OPENING, {"signal": None, "opening": True})
        store.log_event(email, "survey_started")
        history = store.messages(cid)
    return {"conversation_id": cid, "messages": history,
            "profile": public_profile(email)}


def turn(email, answer, call_llm) -> dict:
    """Handle one user message. Never raises for a model or parsing problem."""
    answer = (answer or "").strip()[:MAX_ANSWER]
    if not answer:
        return {"ok": False, "error": "empty message"}

    cid = store.open_conversation(email)
    history = store.messages(cid)

    # what we last asked, so the extractor can read a terse reply in context
    asked = qs.asked_signals(history)
    last_q = next((m["content"] for m in reversed(history)
                   if m.get("role") == "assistant"), None)

    store.add_message(cid, "user", answer)
    store.log_event(email, "survey_message_sent", {"chars": len(answer)})

    profile = load_profile(email)

    observation, err = extractor.extract(call_llm, last_q, answer, history)
    if err:
        store.log_event(email, "profile_extraction_failed", {"reason": err})
    else:
        profile = types.merge_profile(profile, observation)

    profile["questions_answered"] = int(profile.get("questions_answered") or 0) + 1
    profile["scores"] = scorer.score(profile)
    profile["confidence"] = scorer.confidence(profile)
    profile["identifiers"] = identifiers.build(profile)
    profile["adaptation"] = adaptation.builder_defaults(profile)
    store.save_profile(email, profile)
    if not err:
        store.log_event(email, "profile_updated",
                        {"signals": list((profile.get("signals") or {}).keys())})

    # next question — rules only
    history_now = store.messages(cid)
    asked = qs.asked_signals(history_now)
    signal, text = qs.next_question(profile, asked)

    # Once the survey is complete, keep talking like a person rather than
    # replaying the closing line at every further message. Someone who carries
    # on after the last question is refining their profile, not restarting it.
    post_close = signal is None and _already_closed(history_now)
    if post_close:
        text = _acknowledge(profile)

    # Voice anything except the one-time closing line, which is fixed on purpose.
    reply = _voice(call_llm, text, answer, signal, speak=(signal is not None or post_close))

    store.add_message(cid, "assistant", reply,
                      {"signal": signal, "closing": signal is None})

    done = signal is None
    return {
        "ok": True,
        "reply": reply,
        "done": done,
        "profile": public_profile(email, profile),
        "extraction_ok": err is None,
    }


def _already_closed(history) -> bool:
    return any((m.get("meta") or {}).get("closing") for m in history or [])


def _acknowledge(profile) -> str:
    """Reply for a message that arrives after the survey is already complete."""
    action = identifiers.next_best_action(profile)
    pct = int(round(100 * float(profile.get("confidence") or 0.0)))
    return ("Noted — I've added that to your profile, now {}% complete. {} "
            "You can keep going, or {} whenever you're ready."
            ).format(pct, action.get("reason", ""), action.get("label", "carry on").lower())


def _voice(call_llm, question, answer, signal, speak=True):
    """Ask the scripted question in Surveyor's voice, acknowledging the answer.

    If the model is unavailable we send the scripted line verbatim. It reads a
    little flatter, but the conversation continues — the alternative is an error
    message where a question should be, which ends the session.
    """
    if not speak:
        return question
    try:
        user = (f"They just said: {answer!r}\n\n"
                f"Acknowledge that briefly, then ask this, in your own words:\n{question}")
        out = (call_llm(prompts.SURVEYOR_SYSTEM, user, max_tokens=160) or "").strip()
        # a model that ignores the brief and writes an essay gets overridden
        if out and len(out) < 400:
            return out
    except Exception:
        pass
    return question
