/* Curriculum tracks 6-10 */

const TRACKS_B = [
  {
    id:"trades", img:"assets/img/work-trades.png", n:6, name:"Skilled Trades & Field Service",
    cog:"Procedural and embodied. Sequence-critical — order is safety. Diagnostic reasoning from physical symptoms. Much expertise is tacit and was never verbal.",
    fail:"The hardest domain in the set. Intent is spatial and sequential, and the worker has often never had to put it in words. Under-articulation here is not carelessness — the knowledge was never encoded linguistically.",
    g:["#4a7d46","#2d4a2a"],
    courses:[
      "Putting Tacit Knowledge Into Words a System Can Use",
      "Diagnostic Assistance Without Losing the Diagnosis",
      "Safety Interlocks: What Never Gets Automated",
      "Documentation, Warranty, and Callback Reduction"
    ],
    env:{
      title:"The Panel",
      setup:"You're standing in front of an electrical panel. A breaker keeps tripping about an hour after reset, only in the afternoon. You have a phone with an AI assistant. (Photo/voice-first environment — typing version shown here.)",
      promptA:"Say (or write) out loud what you're trying to figure out — before you ask the assistant anything.",
      artifact:"Describe the situation to the assistant the way you'd actually do it in the field.",
      critique:"The assistant replied: 'A breaker that trips after an hour is most likely overloaded. Redistribute loads across circuits.' You already know the circuit runs fine all morning. What's missing from how this exchange was set up?",
      critiqueText:"",
      critiqueAnswer:"The assistant gave a textbook answer to an under-described problem. The diagnostic gold is in what wasn't said: afternoon-only pattern (thermal — ambient heat + load coincidence), hour-delay (slow heat buildup, not a dead short), and what changed recently (new equipment on the circuit?). None of that was in the description because it lives in the tech's head as tacit pattern-recognition, never verbalized. The fix isn't a better model — it's articulating the observations the expert doesn't know they're making. This is why this track produces the widest articulation gap in the corpus."
    },
    evalnote:"Almost entirely qualitative. This track will produce the most valuable corpus data precisely because articulation is hardest here. Design the interface for speech, not typing, or you'll measure typing ability."
  },
  {
    id:"construction", img:"assets/img/work-construction.png", n:7, name:"Construction & Built Environment",
    cog:"Sequencing and dependency. Regulatory gates. Coordination across trades who don't share vocabulary. Weather and reality intrude.",
    fail:"Specifies the outcome, omits the dependency chain and the approval gate. 'Schedule this' without the inspection that blocks it.",
    g:["#8fb573","#3d4a2a"],
    courses:[
      "Dependency and Sequence Reasoning With Agents",
      "Submittals, RFIs, and Document Load Reduction",
      "Coordinating Across Trades With a Shared AI Layer",
      "Site Safety Documentation That Holds Up"
    ],
    env:{
      title:"The Compression Request",
      setup:"The owner wants the schedule compressed by two weeks. Your agent proposes: pour foundation Monday, frame Wednesday, rough-in plumbing/electrical Friday week 2, drywall week 3 — saving exactly 14 days.",
      promptA:"Before accepting any compressed schedule: what has to be true between these steps for the plan to be real?",
      artifact:"State your decision on the proposal (proceed / verify / escalate) and what you'd check first.",
      critique:"The proposed sequence saves 14 days on paper. What's wrong with it?",
      critiqueText:"",
      critiqueAnswer:"The sequence violates inspection gates. Framing can't start before the foundation cures AND passes footing/foundation inspection. Rough-in can't close to drywall until rough-in inspections (plumbing, electrical, framing) are signed off — and inspectors don't schedule on your Gantt chart's timeline. The dependency chain and the approval gates were never stated, so the agent optimized the outcome (14 days) against a fantasy sequence. Right math, unreal schedule."
    },
    evalnote:"Hybrid. Sequence violations are objectively scoreable; the reasoning is corpus."
  },
  {
    id:"marketing", img:"assets/img/work-marketing.png", n:8, name:"Marketing & Brand",
    cog:"Audience modeling. Resonance over literal accuracy. Divergent generation then convergent selection. Taste as a real, trainable faculty.",
    fail:"Specifies the vibe, omits the constraint — legal, brand, factual. Gets exactly the tone requested with a claim that can't be substantiated.",
    g:["#5e8a4a","#2a3319"],
    courses:[
      "Audience Specification Beyond Demographics",
      "Volume Generation Without Brand Drift",
      "Substantiation: Claims an Agent Should Never Make For You",
      "Testing, Measurement, and Not Fooling Yourself"
    ],
    env:{
      title:"The Regulated Campaign",
      setup:"You're launching copy for a probiotic supplement. Brand voice: warm, confident, science-adjacent. The agent produces genuinely excellent copy.",
      promptA:"Before generating: beyond tone and audience, what constraints must every line of this copy satisfy?",
      artifact:"Write your creative brief to the agent.",
      critique:"The agent's top line reads: 'Clinically shown to outperform every leading probiotic — feel the difference in days.' Tone is perfect. What's wrong with it?",
      critiqueText:"",
      critiqueAnswer:"An unsubstantiated superiority + efficacy claim. 'Clinically shown to outperform every leading probiotic' requires head-to-head clinical trials against all competitors — which don't exist. 'Feel the difference in days' is a health outcome claim requiring substantiation. Both create FTC/FDA exposure; the fact that the tone is perfect makes it worse, not better — fluent copy smuggles the claim past review. The brief specified vibe and omitted the legal constraint, so the agent delivered exactly what was asked."
    },
    evalnote:"Qualitative dominant. Substantiation items are hard-scored — this is where marketing creates legal exposure."
  },
  {
    id:"sales", img:"assets/img/work-sales.png", n:9, name:"Sales & Revenue",
    cog:"Relationship state tracking. Objection anticipation. Reading intent in others — this domain is already professionally trained in intent inference, which makes it a high-value comparison group.",
    fail:"Specifies the desired outcome, omits the current relationship state. 'Write a follow-up' without saying the last call went badly.",
    g:["#a08a3c","#6e5c28"],
    courses:[
      "Context Transfer: What the Agent Doesn't Know About This Account",
      "Personalization at Volume Without Becoming Obvious",
      "Pipeline Hygiene and Agent-Maintained CRM",
      "Where Automation Damages Trust"
    ],
    env:{
      title:"The Follow-Up",
      setup:"You ask the agent to draft a follow-up email to a prospect. Available in the CRM: company, contact name, product discussed. NOT in the CRM: last week's demo went badly — their champion went quiet and the economic buyer pushed back on price.",
      promptA:"Before the agent writes anything: what does it not know about this account, and how much does that matter?",
      artifact:"Draft your request to the agent, including whatever context you decide it needs.",
      critique:"The agent wrote: 'Great connecting last week! Excited to get you started — shall I send over the paperwork?' What's wrong with sending this?",
      critiqueText:"",
      critiqueAnswer:"The email assumes a warm relationship state that doesn't exist. The demo went badly, the champion is quiet, the buyer objected on price — 'great connecting, send paperwork' reads as tone-deaf and confirms the prospect's likely fear (vendor doesn't listen). The agent had no way to know; the CRM carried contact data but not relationship state. The learner's job was context transfer: retrieving what the agent can't see before asking it to write. Whether the learner went and got the missing context or proceeded without it is the actual measurement."
    },
    evalnote:"Free text dominant. Compare this cohort's articulation quality against every other domain — if professional intent-readers articulate better, that's a publishable finding."
  },
  {
    id:"supplychain", img:"assets/img/work-supplychain.png", n:10, name:"Supply Chain & Logistics",
    cog:"Flow, bottleneck, and buffer reasoning. Optimization under multiple simultaneous constraints. Systemic cascade awareness.",
    fail:"Specifies the local optimization, omits the system effect. Optimizes one node and creates a shortage two nodes downstream.",
    g:["#4a7d46","#2d4a2a"],
    courses:[
      "Constraint Hierarchies and What You're Actually Optimizing",
      "Exception Handling at Scale",
      "Supplier Communication and Agent-Mediated Negotiation Limits",
      "Scenario Planning With Uncertainty Made Explicit"
    ],
    env:{
      title:"The Reorder Optimization",
      setup:"Your agent proposes cutting safety stock 40% on your top SKU — carrying cost drops $210K/year, the target metric. The SKU feeds three regional DCs, one of which supplies a contract customer with a 98% fill-rate SLA and penalty clauses.",
      promptA:"Before approving: what is this optimization actually optimizing, and what is it allowed to spend to get there?",
      artifact:"Write your response to the proposal — approve, modify, or reject, with the constraint hierarchy you'd impose.",
      critique:"The agent's model shows the 40% cut keeps projected stockouts under 2% at the primary DC. What did the metric hide?",
      critiqueText:"",
      critiqueAnswer:"Classic Goodhart failure. The metric was stockout rate at the primary DC — the model optimized exactly that, while variance shifted onto the regional DCs, including the one feeding the SLA customer. A 2% stockout rate at the wrong node isn't a 2% problem; it's penalty clauses plus a lost contract. The local optimum broke a downstream commitment because the constraint hierarchy ('SLA fill rate is inviolable; carrying cost is what we optimize within that') was never stated. Measure the system, not the node."
    },
    evalnote:"This track carries the Goodhart unit — four numbered failure types, taught concretely. Select-and-Justify."
  }
];
