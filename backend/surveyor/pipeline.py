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

from . import (adaptation, extractor, freeform, identifiers, prompts,
               question_strategy as qs, scenarios, scorer, store, types)

MAX_ANSWER = 4000

# Which hidden criterion a directly-chosen signal counts as evidence for.
# Mirrors scorer._FROM_SIGNALS / _FROM_CATEGORY; kept here so a tapped answer
# records evidence with the same shape an extracted one would.
_CRITERION_FOR = {
    "graph_preference": "visual_systems_thinking",
    "drawing_preference": "visual_systems_thinking",
    "visual_preference": "visual_systems_thinking",
    "verbal_preference": "intent_clarity",
    "risk_awareness": "risk_boundary_awareness",
    "delegation_style": "delegation_readiness",
    "verification_preference": "verification_instinct",
    "correction_style": "gap_detection",
    "interface_density": "constraint_setting",
    "preferred_workspace": "visual_systems_thinking",
    "role_tendency": "domain_specificity",
}


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
    # Re-derive the outstanding step rather than trusting stored meta, so a
    # conversation started before stages existed still resumes correctly.
    profile = load_profile(email)
    step = qs.next_step(profile, qs.asked_signals(history))
    return {"conversation_id": cid, "messages": history,
            "stage": step["stage"],
            "signal": step["key"] if step["stage"] == "preferences" else None,
            "key": step["key"],
            "options": step["options"],
            "profile": public_profile(email, profile)}


def turn(email, answer, call_llm, choice=None) -> dict:
    """Handle one user message. Never raises for a model or parsing problem.

    ``choice`` is {"signal": ..., "value": ...} when the person tapped one of
    the offered answers instead of typing. That path skips extraction entirely:
    there is nothing to infer when someone has pointed directly at the answer,
    and inference is the least reliable part of this pipeline.
    """
    answer = (answer or "").strip()[:MAX_ANSWER]
    if not answer:
        return {"ok": False, "error": "empty message"}

    cid = store.open_conversation(email)
    history = store.messages(cid)

    # what we last asked, so the extractor can read a terse reply in context
    asked = qs.asked_signals(history)
    last_q = next((m["content"] for m in reversed(history)
                   if m.get("role") == "assistant"), None)

    # A chip is only honoured if it matches the signal we actually just asked
    # about and a value we actually offered. The browser is not trusted to name
    # either one.
    picked = None
    if isinstance(choice, dict):
        sig, val = choice.get("signal"), choice.get("value")
        last_sig = next((( m.get("meta") or {}).get("signal")
                         for m in reversed(history) if m.get("role") == "assistant"), None)
        if sig == last_sig and qs.valid_choice(sig, val):
            picked = (sig, val)

    store.add_message(cid, "user", answer, {"choice": bool(picked)})
    store.log_event(email, "survey_message_sent",
                    {"chars": len(answer), "tapped": bool(picked)})

    profile = load_profile(email)
    err = None

    # Which stage the outstanding question belonged to, so the answer is filed
    # in the right place rather than guessed at.
    last_meta = next((m.get("meta") or {} for m in reversed(history)
                      if m.get("role") == "assistant"), {})
    stage, key = last_meta.get("stage"), last_meta.get("key")

    if stage == "scenarios" and key:
        val = (choice or {}).get("value") if isinstance(choice, dict) else None
        if scenarios.valid_choice(key, val):
            answers = dict(profile.get("scenarios") or {})
            answers[key] = val
            profile["scenarios"] = answers
            store.log_event(email, "scenario_answered", {"scenario": key, "value": val})
        else:
            # Typed instead of tapped. We deliberately do NOT infer which option
            # they meant: a scenario is only worth anything if the choice is
            # exact, and a guessed one would corrupt the stated-vs-revealed
            # comparison that this whole stage exists to produce.
            store.log_event(email, "scenario_freetext", {"scenario": key})

    elif stage == "freeform" and key:
        text = freeform.clean(answer)
        if text:
            answers = dict(profile.get("freeform") or {})
            answers[key] = text
            profile["freeform"] = answers
            store.log_event(email, "freeform_answered",
                            {"key": key, "chars": len(text)})

    elif picked:
        sig, val = picked
        signals = dict(profile.get("signals") or {})
        signals[sig] = val
        profile["signals"] = signals
        profile["evidence"] = (list(profile.get("evidence") or []) + [{
            "criterion": _CRITERION_FOR.get(sig, "intent_clarity"),
            "summary": f"Chose “{qs.label_for(sig, val)}”.",
            "confidence": "high",
            "source": "surveyor_conversation",
        }])[-60:]
    else:
        observation, err = extractor.extract(call_llm, last_q, answer, history)
        if err:
            store.log_event(email, "profile_extraction_failed", {"reason": err})
        else:
            profile = types.merge_profile(profile, observation)

    profile["questions_answered"] = int(profile.get("questions_answered") or 0) + 1
    profile["scores"] = scorer.score(profile)
    # progress bar spans all three stages; scorer.confidence only knows stage 1
    profile["confidence"] = types.profile_completeness(profile)
    profile["identifiers"] = identifiers.build(profile)
    profile["tensions"] = scenarios.find_tensions(profile.get("signals"),
                                                  profile.get("scenarios"))
    profile["reliability"] = scenarios.reliability(profile["tensions"])
    profile["adaptation"] = adaptation.builder_defaults(profile)
    store.save_profile(email, profile)
    if not err:
        store.log_event(email, "profile_updated",
                        {"signals": list((profile.get("signals") or {}).keys())})

    # next step — rules only, across all three stages
    history_now = store.messages(cid)
    asked = qs.asked_signals(history_now)
    step = qs.next_step(profile, asked)
    done = step["stage"] == "done"

    # Once the survey is complete, keep talking like a person rather than
    # replaying the closing line at every further message. Someone who carries
    # on after the last question is refining their profile, not restarting it.
    post_close = done and _already_closed(history_now)
    text = _acknowledge(profile) if post_close else step["text"]
    if step.get("intro"):
        text = step["intro"] + "\n\n" + text

    # Voice anything except the one-time closing line, which is fixed on purpose.
    reply = _voice(call_llm, text, answer, step["key"],
                   speak=(not done or post_close))

    store.add_message(cid, "assistant", reply, {
        "stage": step["stage"], "key": step["key"],
        "signal": step["key"] if step["stage"] == "preferences" else None,
        "closing": done,
    })

    return {
        "ok": True,
        "reply": reply,
        "done": done,
        "stage": step["stage"],
        "signal": step["key"] if step["stage"] == "preferences" else None,
        "key": step["key"],
        "options": step["options"],
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
