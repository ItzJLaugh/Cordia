/* CordiaAIE Course 1 — Saying What You Mean. Drafted by Claude Code, mounted by SOUL. */
const COURSE_AIE1 = {
 "id": "aie1",
 "code": "CordiaAIE-1",
 "title": "Saying What You Mean",
 "modules": [
  {
   "short": "Spot the Gap",
   "title": "Module 1: Spot the Gap",
   "html": "<p>An agent does exactly what you say — not what you meant. \"Clean up this spreadsheet.\" \"Handle the vendor email.\" \"Make the schedule work.\" These sound like instructions. They're actually invitations to guess. And if that agent is directing other agents underneath it, everyone downstream inherits the guess before anyone catches it.</p><p>This course isn't about learning agent syntax. It's about noticing, in your own head, the gap between what you're picturing and what you actually said out loud. That gap is where things go wrong — not because the agent isn't smart enough, but because it was never told.</p><p><b>The test:</b> could a competent stranger, doing *exactly* what you wrote and nothing more, produce something you'd accept without fixing it? If you had to imagine them making a judgment call to get it right, that call was yours to make — and you skipped it.</p>",
   "exercises": [
    {
     "kind": "cold intent",
     "prompt": "You supervise an agent that manages patient intake scheduling. Write the instruction you'd give it to fix: \"the schedule keeps double-booking Dr. Malik on Tuesdays.\"",
     "rubric": "**0-missing:** restates the problem (\"fix the double-booking\"). **1-vague:** names the outcome, no rule (\"don't let Malik get double-booked\"). **2-specific:** gives the agent a rule — what counts as a conflict, what to do about it (\"block any new Tuesday slot that overlaps an existing one; flag it to me, don't auto-resolve\"). **3-falsifiable:** adds a way to check the work (\"...and list today's Tuesday slots with any remaining overlaps so I can confirm there are none\"). Reward rules over restated goals."
    },
    {
     "kind": "critique seeded output",
     "prompt": "An office manager told her assistant agent: \"Make the vendor invoice tracker better.\" The agent added three columns and reformatted every date. Was the agent wrong? In 2–3 sentences, explain what happened, then rewrite the instruction.",
     "rubric": "Good answers recognize the agent wasn't wrong — \"better\" had no definition, so it invented one. A fix names what \"better\" means: \"I want to see which invoices are 10+ days overdue at a glance — add a column that flags that, don't touch anything else.\" Flag any answer that blames the agent instead of the instruction."
    },
    {
     "kind": "light escalation",
     "prompt": "You tell your scheduling agent \"handle it\" for a shift-swap request between two electricians. It could approve outright, ask you first, or tell the workers to sort it out themselves. Write the instruction that tells it which one you want — and why.",
     "rubric": "Look for a stated *decision rule*, not just a picked option (\"approve automatically if it doesn't create overtime, otherwise ask me\"). A rule is falsifiable — later, you can check whether the agent actually followed it."
    }
   ]
  },
  {
   "short": "Name the Target",
   "title": "Module 2: Name the Target",
   "html": "<p>\"Good\" isn't something an agent can see in your head — it's a description of a check. \"Make it professional,\" \"make it thorough,\" \"handle it well\" — none of these tell an agent what to actually verify before calling the job done. So it doesn't verify anything. It stops when the output looks finished to itself, which is not the same as finished to you.</p><p>Success criteria is the specific thing you'd look at afterward to decide whether the work succeeded. Sometimes it's a number (\"all 12 line items included, not just the ones over $500\"). Sometimes it's a comparison (\"matches the format of the last three quotes we sent this client\"). Sometimes it's the absence of something (\"no line item without a corresponding PO number\"). The common thread: you could hand your criteria to a stranger and they could check the output against it without asking you anything else.</p><p>Here's the part that surprises people: naming success criteria isn't extra work. You were always going to check the output — that's what \"reviewing\" an agent's work means. Naming the criteria just moves that same checking work earlier, into the instruction, so the agent can catch its own mistakes before they ever reach you. A vague instruction doesn't save you time; it just moves the checking to the end, after the damage is already done and harder to undo.</p><p>One more distinction worth having: criteria that catch a problem *before* it happens (a threshold, a required approval, a flag) are worth more than criteria that only describe the finished output, because they give the agent a way to stop itself partway through instead of just producing a wrong thing faster. This is the same idea as \"falsifiable\" from Module 1 — a criterion you could actually fail is one that's doing real work. \"Make it good\" can't be failed. \"Under 150 words and references the last quote date\" can.</p>",
   "exercises": [
    {
     "kind": "cold intent",
     "prompt": "You need an agent to draft a follow-up email to a client who hasn't responded in two weeks. Write the instruction — including how you'd know afterward whether the email succeeded.",
     "rubric": "**0-missing:** no success criteria at all. **1-vague:** \"make it professional and friendly\" — unmeasurable adjectives. **2-specific:** \"reference the last quote date, ask a single yes/no question, keep it under 150 words.\" **3-falsifiable:** ties criteria to the actual goal, not just the email's appearance (\"success = client replies with a decision, not just an acknowledgment; if no reply in 5 days, flag it to me instead of sending a second follow-up automatically\")."
    },
    {
     "kind": "select + justify",
     "prompt": "Two candidate instructions for an agent drafting a nurse's end-of-shift handoff note:\n**(a)** \"Summarize today's patient status for the next nurse.\"\n**(b)** \"List each patient's current pain level, any medication given in the last 2 hours, and anything the next nurse needs to check in their first hour — flag any patient where the information might be incomplete.\"\nWhich would you trust to catch a missed medication? Explain what makes the difference.",
     "rubric": "Full credit identifies (b): it names specific, checkable items instead of leaving \"summarize\" to the agent's discretion, and the self-flagging clause turns uncertainty into a visible check instead of a silent guess."
    },
    {
     "kind": "live task with revision",
     "prompt": "You told an agent: \"Reorder inventory for anything running low.\" It restocked 40 SKUs, including a $12,000 order for a seasonal item you don't want this month. What went wrong, and rewrite the instruction with success criteria that would have caught this before the order went out.",
     "rubric": "Strong answers separate \"what counts as low\" (a threshold) from \"what confirms this is a good buy\" (a check against seasonality or budget) — e.g., requiring approval above a dollar threshold, or excluding designated seasonal SKUs. A checkable gate, not \"use good judgment.\""
    }
   ]
  },
  {
   "short": "Delegate on Purpose",
   "title": "Module 3: Delegate on Purpose",
   "html": "<p>Not every decision needs you. Not every decision should skip you either. The skill in this module is telling the difference — especially once your agent isn't just doing the work itself, but handing pieces of it to other agents underneath it.</p><p>When one agent is directing several others, you're no longer just instructing a worker — you're instructing a manager. And a manager, human or otherwise, will make dozens of small calls a day about what to assign, in what order, and when to escalate. You can't review all of them, and you shouldn't try. Trying turns you into the bottleneck, which defeats the point of delegating in the first place.</p><p>The judgment call is choosing checkpoints: specific points in the chain where the work must pause and show you something before it continues. Not \"check in with me\" generally — that just recreates the vague-instruction problem from Module 1, one layer down. A good checkpoint names the exact condition that triggers it.</p><p>How do you pick where the checkpoints go? Look for decisions that are expensive to undo, that affect someone outside the process — a patient, a customer, someone else's money or schedule — or that lock in something hard to walk back later. A missed inspection date is worth a checkpoint. Which font a drafting agent picks is not. The test isn't \"is this unfamiliar to me\" — it's \"is this hard to undo if it's wrong.\"</p><p>Two traps sit on either side of this. Checkpoint everything, and you've built a system that can't move without you — you'll end up approving things you don't understand well enough to actually evaluate, and the delegation was pointless. Checkpoint nothing, and you find out something went wrong only after two or three agents have already acted on it, and the fix costs more than the original task did.</p><p>The instruction that avoids both traps names the specific trigger and lets everything else run: not \"check everything with me,\" and not \"handle it,\" but \"this kind of decision comes to me; everything else, proceed.\"</p>",
   "exercises": [
    {
     "kind": "cold intent",
     "prompt": "Your triage agent reads incoming contracts. For routine ones, it tells a second \"drafting agent\" to prepare a standard reply; for unusual ones, it's supposed to escalate. Write the instruction that tells your triage agent exactly when to let the drafting agent proceed on its own, and when to stop and show you first.",
     "rubric": "**0-missing:** \"handle routine ones, escalate anything weird\" — no definition of weird. **2-specific:** a concrete trigger (\"any clause changing payment terms, liability, or termination rights comes to me first; everything else can proceed\"). **3-falsifiable:** closes the loophole for uncertainty (\"if the triage agent is unsure whether a clause counts, treat it as escalate, not proceed\")."
    },
    {
     "kind": "select + justify",
     "prompt": "A coordinator agent assigns subcontractor scheduling to trade-specific agents (electrical, plumbing, drywall). Two checkpoint designs:\n**(a)** The coordinator must get your approval before assigning any task to a sub-agent.\n**(b)** The coordinator can assign freely, but any change to the drywall start date needs your approval first, since it's tied to a fixed inspection appointment.\nWhich would you choose — and why does it matter that it's specifically the drywall date, not \"any date\"?",
     "rubric": "Full credit picks (b) and explains that (a) makes you a bottleneck for trivial decisions, while (b) places the human check exactly where a mistake is expensive and hard to reverse — and nowhere else."
    },
    {
     "kind": "escalation",
     "prompt": "Your outreach agent directs a smaller drafting agent to send personalized follow-ups to leads. One lead replies wanting to *cancel* their existing contract, not start a new one. Should the drafting agent handle this itself, or stop? Write the instruction you'd add now to prevent this being handled wrong again.",
     "rubric": "Strong answers recognize this is exactly the externally-consequential, hard-to-reverse situation that needs a checkpoint. The instruction should name the trigger (\"any reply mentioning cancellation, complaint, or contract change stops the sequence and comes to me\") — not a vague \"use judgment.\""
    }
   ]
  },
  {
   "short": "Close the Loop",
   "title": "Module 4: Close the Loop",
   "html": "<p>Your first instruction is rarely your last one. Even a well-built instruction — specific, with success criteria, with the right checkpoints — will sometimes come back wrong. That's not failure. That's the normal shape of working with an agent, the same way it's normal when working with a new hire or a contractor you haven't worked with before.</p><p>What matters is what you do next. The instinct is to say \"this isn't right, try again\" or \"fix it.\" Both feel like instructions, but they're really just a vaguer version of the Module 1 problem, aimed at an output instead of a blank page. The agent still has to guess what \"right\" means — you've just made it guess twice.</p><p>The skill here is the same gap-spotting from Module 1, pointed backward: read what came back, and name precisely what's different between that and what you wanted. Not \"the tone is off\" — \"this reads as urgent, I need it to read as routine.\" Not \"you missed something\" — \"add the vendor contract renewal, it's not in here.\" The more your revision sounds like your original success criteria (Module 2's skill), the less the agent has to guess a second time.</p><p>A useful loop: Read the output. Name the gap — specifically, in the same terms you'd use for success criteria. Re-instruct with just the delta, not the whole task over again. Recheck against your original criteria, not against how close it *feels* to right.</p><p>One more thing worth catching: sometimes the same mistake will recur if you only fix the one output in front of you. If an agent keeps missing the same category of thing, the real gap isn't in this result — it's in the definition it's working from. Fixing that definition once is worth more than fixing ten outputs one at a time.</p><p>And when work has passed through more than one agent — a coordinator handing tasks to specialists, from Module 3 — the same question applies to your revision: is the fix needed at the layer that produced the output, or one layer up, where the wrong input got handed down in the first place? Sending the same patch to the wrong layer means you'll be sending it again next week.</p>",
   "exercises": [
    {
     "kind": "live task with revision",
     "prompt": "You asked an agent to draft a meeting agenda for a budget review. It comes back with 8 items, but two are unrelated topics pulled from an old email thread, and it's missing the vendor contract renewal you specifically need discussed. Write the revision instruction you'd send back.",
     "rubric": "**0-missing:** \"this is wrong, redo it.\" **1-vague:** \"remove what doesn't belong and add what's missing\" — no specifics. **2-specific:** names the exact items (\"remove items 5 and 7 — they're from the March thread; add 'vendor contract renewal — decision needed' as item 1\"). **3-falsifiable:** adds a rule preventing recurrence (\"when pulling agenda items, only use messages tagged 'budget review,' not the general thread\")."
    },
    {
     "kind": "critique seeded output",
     "prompt": "An agent summarizing a patient's chart for handoff writes: \"Patient stable, no major changes.\" The chart actually shows a new medication started 3 hours ago. What's wrong with revising this by just saying \"add the medication note\"? Write a revision instruction that also prevents the miss from happening again.",
     "rubric": "Full credit recognizes that patching this one output doesn't address *why* \"no major changes\" was said despite a new medication — the real gap is the agent's definition of \"major change.\" Strong answers redefine it explicitly (\"any new medication in the last 12 hours counts as a major change\"), not just fix the one instance."
    },
    {
     "kind": "escalation + revision, layered",
     "prompt": "An estimating agent — working under a coordinator agent that also manages two other trade agents — sends you a quote 30% higher than your usual range for this job type. Do you re-instruct the estimating agent directly, or go to the coordinator? Write what you'd say, and to which one.",
     "rubric": "Strong answers consider whether the error originates upstream — e.g., the coordinator passed the wrong job scope to the estimator — and address the coordinator directly if so (\"this job type usually runs X, this bid is 30% over — check what scope you sent the estimator\"), rather than patching only the estimator's output and having the same wrong input recur next time. Reinforces Module 3's layer-awareness applied to revision."
    }
   ]
  }
 ]
};
