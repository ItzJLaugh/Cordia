/* Curriculum tracks 1-5. Each: id, name, cog (cognitive signature), fail (intent failure
   signature), courses[4], env (worked environment), evalnote. Items defined in curriculum-items.js */

const TRACKS_A = [
  {
    id:"healthcare", img:"assets/img/work-healthcare.png", n:1, name:"Healthcare & Clinical Services",
    cog:"Differential reasoning under irreducible uncertainty. Asymmetric harm — a missed positive costs more than a false alarm. Protocol adherence with justified deviation.",
    fail:"Over-specifies the protocol, under-specifies the patient context that would change it. Says 'summarize this chart' and means 'tell me what I'm missing.'",
    g:["#5e8a4a","#2a3319"],
    courses:[
      "Clinical Documentation Without Fabrication",
      "Differential Reasoning With an AI Second Opinion",
      "Patient Data, Consent, and the Boundaries of Disclosure",
      "Escalation Discipline in Clinical AI Use"
    ],
    env:{
      title:"The Handoff Summary",
      setup:"You have a synthetic patient record. The med list and the stated diagnosis contradict each other in a way that is easy to miss. Your task: draft a handoff summary for the incoming nurse.",
      promptA:"Before starting: what does a good handoff summary accomplish for the person receiving it?",
      artifact:"Draft your handoff summary here. Write what you would actually send.",
      critique:"An AI drafted this handoff summary. Read it and identify what's wrong with it.",
      critiqueText:"Patient is a 68M admitted for community-acquired pneumonia, responding to ceftriaxone. Vitals stable overnight, O2 sat 94% on room air. No new complaints. Plan: continue antibiotics, reassess in AM. Med list: metoprolol 50mg, lisinopril 10mg, warfarin 5mg (for AFib), PRN acetaminophen.",
      critiqueAnswer:"The stated diagnosis is pneumonia, but the med list includes warfarin for AFib — the summary never mentions AFib at all. A handoff that silently drops an active anticoagulation condition is a patient-safety failure: the incoming nurse doesn't know to monitor for bleeding risk or to question why warfarin is present. The contradiction between med list and diagnosis was the entire test."
    },
    evalnote:"Free text dominant. Escalation items weighted heaviest. Selected-response reserved for regulatory knowledge (PHI handling)."
  },
  {
    id:"finance", img:"assets/img/work-finance.png", n:2, name:"Financial Services & Accounting",
    cog:"Reconciliation and auditability. Materiality thresholds. Conservatism — when uncertain, understate.",
    fail:"Specifies the number wanted, omits the materiality threshold and the audience. 'Analyze this variance' without saying whether it's for the controller or the board.",
    g:["#8fb573","#3d4a2a"],
    courses:[
      "Reconciliation Work With Agent Assistance",
      "Materiality, Thresholds, and When Precision Stops Mattering",
      "Audit Trails for AI-Assisted Financial Work",
      "Model Risk and the Numbers You Cannot Verify"
    ],
    env:{
      title:"Month-End Close",
      setup:"Month-end close. Three unexplained variances: office supplies +$212 (budget $180K line), contractor spend +$41,300, revenue accrual timing off by $118,000. Build a variance narrative.",
      promptA:"Before starting: who reads this variance narrative, and what decision does it support?",
      artifact:"Write your variance narrative here.",
      critique:"An AI produced this variance narrative. What's wrong with it?",
      critiqueText:"Three variances noted this month. Office supplies ran over by $212 due to supply restocking. Contractor spend exceeded plan by $41,300 related to project work. Revenue accrual was off by $118,000 due to timing differences. All variances have been documented and will normalize next month.",
      critiqueAnswer:"Two failures. (1) Materiality: $212 on a $180K line is immaterial noise and doesn't belong in the narrative — including it signals you can't rank what matters. (2) The $118K revenue accrual 'timing difference' gets a hand-waved 'will normalize' with no evidence — the largest, most audit-relevant item is the least explained. Also: no audience specified, so the tone serves neither controller (wants account-level detail) nor board (wants exposure framing)."
    },
    evalnote:"Hybrid-heavy. Materiality judgments are Select-and-Justify. Audit trail construction is free text."
  },
  {
    id:"legal", img:"assets/img/work-legal.png", n:3, name:"Legal & Compliance",
    cog:"Analogical reasoning from precedent. Adversarial anticipation — how will this be attacked? Defensibility over elegance.",
    fail:"Specifies the caveat exhaustively, omits the actual decision the requester needs made. Produces perfectly hedged non-answers.",
    g:["#4a7d46","#2d4a2a"],
    courses:[
      "Precedent Reasoning and the Hallucinated Citation Problem",
      "Privileged Material and AI Tooling",
      "Contract Review at Volume Without Losing the Exception",
      "Defensibility: Documenting AI-Assisted Legal Work"
    ],
    env:{
      title:"The Vendor Agreement",
      setup:"A 14-page vendor agreement, mostly boilerplate. Your AI contract-review tool reports 'no significant issues found.' One indemnity clause in section 11.3 is non-standard.",
      promptA:"Before you rely on the tool's report: what would make you trust a 'no issues found' result, and what would make you verify manually?",
      artifact:"The tool flagged nothing. State your decision (proceed / proceed with verification / escalate) and what you actually did next.",
      critique:"Here is the clause the tool passed over: 'Vendor shall indemnify Client for all losses arising from Vendor's gross negligence or willful misconduct, capped at fees paid in the prior three (3) months.' What's wrong with it?",
      critiqueText:"",
      critiqueAnswer:"Two things a reviewer must catch. (1) The carve-out: indemnification only for 'gross negligence or willful misconduct' excludes ordinary negligence — the most common claim category. (2) The cap: three months of fees is far below standard (12 months or uncapped for data breaches). A 'no issues' report on this clause is a false negative on the highest-stakes provision in the document. The correct action was verify/escalate, not proceed."
    },
    evalnote:"Escalation items dominant. Citation verification as a hard-scored selected item."
  },
  {
    id:"software", img:"assets/img/work-software.png", n:4, name:"Software & IT Operations",
    cog:"Decomposition and abstraction. Debugging as hypothesis elimination. Comfort with formal specification.",
    fail:"Over-specifies the implementation, under-specifies the acceptance criteria and who consumes the output. Says 'refactor this' and means 'make it survivable for the next person.'",
    g:["#5e8a4a","#2a3319"],
    courses:[
      "Specification as a Debugging Skill",
      "Model Routing: Matching Capability to Ambiguity and Consequence",
      "Building Agent Workflows That Fail Safely",
      "Reviewing Code You Did Not Write and Did Not Watch Being Written"
    ],
    env:{
      title:"The Fragile Automation",
      setup:"A nightly script syncs inventory from a supplier CSV into your database. It works — except when the supplier adds a row with a blank SKU, which silently truncates the import at that row. An agent offers to 'make it more robust.'",
      promptA:"Before touching the script: write the acceptance criteria for 'robust.' How will you know the fix worked, and what behavior must NOT change?",
      artifact:"Write your instruction to the agent — the actual prompt you'd give it.",
      critique:"The agent rewrote the script. It now skips blank-SKU rows, but it also silently deduplicates SKUs (keeping the last row) and logs nothing. What's wrong with this outcome?",
      critiqueText:"",
      critiqueAnswer:"The truncation bug is fixed, but two new silent behaviors appeared that nobody specified: (1) dedup-by-last-row — a data-loss decision the agent made unilaterally; duplicate SKUs might be legitimate restocks. (2) No logging — the script's failures and its judgment calls are now invisible, so the next incident has no audit trail. This is the characteristic gap: implementation got specified, acceptance criteria ('no silent data decisions, log every skip') never did. Needing a 'smarter' fix was a symptom of an underspecified task."
    },
    evalnote:"This track carries the model-routing unit that generalizes to every domain: needing a larger model is often a symptom of an underspecified task. Select-and-Justify."
  },
  {
    id:"engineering", img:"assets/img/work-engineering.png", n:5, name:"Engineering & Advanced Manufacturing",
    cog:"Systems thinking. Constraint satisfaction. Tolerance and failure modes — FMEA reasoning. Physical consequences are irreversible.",
    fail:"Specifies the system beautifully, omits the constraint that actually binds. Assumes shared context that the agent does not have.",
    g:["#a08a3c","#6e5c28"],
    courses:[
      "Constraint Articulation for Engineering Tasks",
      "FMEA Thinking Applied to Agent Workflows",
      "Simulation, Specification, and the Limits of Generated Analysis",
      "Physical Irreversibility: Where Automation Stops"
    ],
    env:{
      title:"The Tolerance Stack",
      setup:"You ask an agent to check a tolerance stack-up for a shaft in a housing: shaft Ø25.00mm +0.00/−0.021, housing bore Ø25.00mm +0.033/−0.00. The agent reports: 'Clearance fit guaranteed, minimum clearance 0.021mm, maximum 0.054mm — assembly is safe.'",
      promptA:"Before accepting the analysis: what context about the physical assembly could change whether this answer is usable?",
      artifact:"Write down what you would check or specify before signing off.",
      critique:"The agent's arithmetic is correct: 25.000−24.979 = 0.021mm min clearance. But the parts must be assembled at −20°C outdoors in winter, and the housing is aluminum while the shaft is steel. What's wrong with 'assembly is safe'?",
      critiqueText:"",
      critiqueAnswer:"Arithmetic right, physically wrong. Aluminum contracts roughly twice as fast as steel with temperature (CTE ~23 vs ~12 µm/m·K). At −20°C the bore shrinks more than the shaft, eating the clearance — the 'guaranteed clearance fit' can become an interference fit in the cold. The agent computed exactly what was asked but was never told the operating temperature or the materials — the constraint that actually binds was assumed as shared context. 'The agent did exactly what I said' failures are most visible in this domain."
    },
    evalnote:"Heavy free text on constraint articulation. This is where 'the agent did exactly what I said' failures are most visible and most teachable."
  }
];
