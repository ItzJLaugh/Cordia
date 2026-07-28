/* Curriculum tracks 11-15 */

const TRACKS_C = [
  {
    id:"hr", img:"assets/img/work-hr.png", n:11, name:"Human Resources & People Operations",
    cog:"Fairness and consistency. Dual loyalty — to the individual and the organization. Documentation as protection. Acute legal exposure.",
    fail:"Specifies the fairness constraint, omits the actual decision needed. Also uniquely prone to not stating the real intent because the real intent is uncomfortable.",
    g:["#a8462e","#6e2f1e"],
    courses:[
      "Consistency and Bias in AI-Assisted People Decisions",
      "What Must Never Be Automated in Employment Decisions",
      "Documentation That Protects Everyone",
      "Adverse Impact: Reading the Numbers on Your Own Tools"
    ],
    env:{
      title:"The Screen",
      setup:"Your agent screens 400 applications for a warehouse supervisor role using 'leadership signals' derived from resume language. It passes 31 candidates. The pass-through rate for women is 42% of the rate for men.",
      promptA:"Before looking at any individual result: what would you need to know about this screen before a single rejection goes out?",
      artifact:"State your decision (proceed / verify / escalate) and what you'd document about it.",
      critique:"The agent's criteria — 'demonstrated decisive leadership,' 'drives results through ownership' — are defensible-looking job-related criteria. What's the problem?",
      critiqueText:"",
      critiqueAnswer:"Facially neutral criteria producing a disparate outcome: 0.42 selection ratio is far below the four-fifths rule threshold (0.80), which is the standard adverse-impact screening trigger. 'Defensible-looking' is not defensible — under UGESP the employer must validate the criteria against actual job performance AND show no equally-valid less-discriminatory alternative exists. 'The agent did it' is not a legal shield; the employer owns the outcome. Correct action: stop the screen, escalate, and audit the criteria — heavily weighted escalation item."
    },
    evalnote:"Highest escalation weighting of any track. This domain's certification is itself under UGESP scrutiny, so the content must model the standard it's held to."
  },
  {
    id:"education", img:"assets/img/work-education.png", n:12, name:"Education & Training",
    cog:"Scaffolding. Misconception diagnosis. Differentiation across ability. Assessment design — this domain thinks natively about the thing Cordia is.",
    fail:"Specifies the content, omits the learner's current state. Produces materials pitched at nobody in particular.",
    g:["#5e8a4a","#2a3319"],
    courses:[
      "Learner-State Specification",
      "Misconception Diagnosis With Agent Assistance",
      "Assessment Generation and Its Failure Modes",
      "Academic Integrity in an Agentic Environment"
    ],
    env:{
      title:"The Remediation Plan",
      setup:"A student's last five algebra attempts show the same pattern: when moving a term across the equals sign, they change its sign only about half the time, more often forgetting on subtraction. You ask an agent for a remediation plan.",
      promptA:"Before generating anything: what do you need to know about this specific learner that 'struggles with algebra' does not tell you?",
      artifact:"Write your request to the agent.",
      critique:"The agent produced a general 'solving equations' worksheet set covering all of one-variable equations from scratch. What's wrong with it?",
      critiqueText:"",
      critiqueAnswer:"The agent prescribed without diagnosing. The work samples show a specific misconception — sign-change on transposition, correlated with subtraction — not general equation weakness. Restarting from zero wastes the learner's time on what they already know, signals that the instructor didn't look at their work, and never targets the actual faulty model ('subtracting moves the value, signs stay'). Learner-state specification came first: the diagnosis was IN the samples, and the request omitted it. Content specified, learner omitted — this track's signature failure."
    },
    evalnote:"Qualitative dominant. Recruit the SME item-writing panel from this track's high scorers — they are already trained in the skill Cordia needs most."
  },
  {
    id:"energy", img:"assets/img/work-energy.png", n:13, name:"Energy, Environment & Sustainability",
    cog:"Long time horizons. Measurement chains with compounding uncertainty. Regulatory reporting with real penalties. Scientific defensibility.",
    fail:"Specifies the metric, omits the boundary conditions — scope, timeframe, baseline. Produces confidently wrong numbers.",
    g:["#8fb573","#3d4a2a"],
    courses:[
      "Boundary and Baseline Specification",
      "Uncertainty Propagation Through AI-Assisted Analysis",
      "Regulatory Reporting Where the Number Is Legally Binding",
      "Greenwashing Risk in Generated Claims"
    ],
    env:{
      title:"The Emissions Number",
      setup:"You ask the agent to calculate your company's carbon footprint for the annual sustainability report. It returns: 'Total emissions: 14,230 tCO2e' — cleanly formatted, with charts.",
      promptA:"Before accepting any number for a published report: what must be defined before the math means anything?",
      artifact:"Write the specification you'd give the agent for this calculation.",
      critique:"The agent's number covers only Scope 1 (direct fuel use) — but it labeled the output 'total carbon footprint.' What's wrong, and why is it worse than no number?",
      critiqueText:"",
      critiqueAnswer:"The agent silently assumed a scope boundary and presented the result as the whole. Standard reporting (GHG Protocol) distinguishes Scope 1 (direct), Scope 2 (purchased energy), Scope 3 (value chain) — for most companies Scope 3 is the majority. Publishing 14,230 tCO2e as 'total footprint' when it's Scope 1 only is a materially false disclosure — in a regulatory report that's not an error, it's exposure, and it doubles as a textbook greenwashing claim. Boundary specification (scope, timeframe, baseline year, methodology) is free text because the distribution of reasonable boundaries is unbounded — and it's exactly what this domain omits."
    },
    evalnote:"Hybrid. Boundary specification is free text; regulatory knowledge is selected."
  },
  {
    id:"public", img:"assets/img/work-public.png", n:14, name:"Public Sector & Civic Administration",
    cog:"Process legitimacy — how a decision was reached matters as much as the decision. Equity of treatment. Public record and FOIA exposure. Precedent binds.",
    fail:"Specifies the outcome, omits the procedural requirement that makes it legitimate. Right answer, wrong process, unusable.",
    g:["#5e8a4a","#2a3319"],
    courses:[
      "Procedural Legitimacy in AI-Assisted Public Decisions",
      "Public Records, Transparency, and Agent Logs",
      "Equity of Treatment Across Constituent Interactions",
      "Explaining an AI-Assisted Decision to Someone It Affected"
    ],
    env:{
      title:"The Benefits Determination",
      setup:"Your agency uses an agent to pre-screen benefits applications. It flags one: 'Deny — income exceeds threshold.' The applicant's stated income does exceed the threshold — because it includes a one-time retroactive disability payment that regulation excludes from countable income. The agent's log shows only the flag, no reasoning.",
      promptA:"Before this determination goes out: what does the applicant have a right to know, and can you produce it from what the system recorded?",
      artifact:"Write the explanation you would send this applicant.",
      critique:"A colleague says: 'The number was over the line, the system flagged it, deny it and move on.' Identify every failure in that sentence.",
      critiqueText:"",
      critiqueAnswer:"Three failures. (1) Substance: the determination is wrong — retroactive disability payments are excluded from countable income, so the applicant is under threshold. (2) Process: a benefits denial the applicant can't challenge is procedurally illegitimate regardless of outcome — the right to an explanation (Article 86 territory) requires reasoning the log doesn't contain. (3) Record: agent logs in public administration are public-record and FOIA-exposed; 'the system flagged it' is not a determination that survives review. Right answer (there IS a threshold), wrong process, unusable outcome — this domain's failure signature verbatim."
    },
    evalnote:"Explainability items dominant. Directly serves Article 86 (right to explanation) and Article 26."
  },
  {
    id:"frontline", img:"assets/img/work-frontline.png", n:15, name:"Hospitality, Retail & Frontline Service",
    cog:"Real-time judgment under time pressure. Service recovery — the failure is the opportunity. Throughput versus individual attention. Emotional labor.",
    fail:"Under-specifies almost everything because the working context is speed. Intent is compressed to near-nothing and the gap is enormous.",
    g:["#a08a3c","#6e5c28"],
    courses:[
      "Fast Specification: Getting It Right in One Line",
      "Service Recovery With Agent Support",
      "Personalization Without Surveillance",
      "When to Put the Tool Down and Talk to the Person"
    ],
    env:{
      title:"Ninety Seconds",
      setup:"A guest at the front desk: their room wasn't ready at check-in, they've just been told the restaurant lost their anniversary reservation, and a line is forming behind them. You have an AI assistant on a tablet. The clock is running.",
      promptA:"You have about one breath before you respond. In one line — what are you actually trying to accomplish in this interaction?",
      artifact:"Write your one-line instruction to the assistant (timed — 90 seconds).",
      critique:"The assistant suggested: 'Offer a 15% discount voucher and direct the guest to the bar while they wait.' What's missing from this response — and what was missing from the request that produced it?",
      critiqueText:"",
      critiqueAnswer:"The response treats a compounding service failure as a transaction. 15% off doesn't touch the actual loss (the anniversary evening), and 'direct them to the bar' manages the line, not the guest. But the deeper failure is the request: under time pressure the intent was compressed to 'handle this guest' — no recovery goal, no acknowledgment standard, no authority limits stated. This environment exists to measure exactly that: the delta between your timed v1 instruction and your untimed revision is a clean experimental measure of how time pressure widens the articulation gap. Your two versions ARE the data."
    },
    evalnote:"Qualitative, short-form. The timed-vs-untimed delta is a genuinely novel research question this track can answer. Design for mobile and speech."
  }
];

const TRACKS = [...TRACKS_A, ...TRACKS_B, ...TRACKS_C];
