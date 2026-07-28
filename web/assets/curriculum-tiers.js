/* Cordia Curriculum — data source of truth
   PART 1: tiers + tracks 1-5. Loaded by training.html, course.html, track.html */

const TIERS = [
  {
    id:"aie", badge:"assets/img/badge-aie.png", code:"CordiaAIE", name:"AI Employee",
    who:"Any worker who uses AI in their job. The Article 4 baseline.",
    claim:"This person can state what they want, recognize when they didn't get it, and knows what not to do.",
    mix:"~55% free text, 30% selected, 15% hybrid",
    signature:"Archetype A + C. A single task, cold intent captured, one revision cycle. Your first corpus record.",
    cut:"Competence, not excellence. Proves safe baseline use — 'would you let this person use AI unsupervised on routine work?'",
    g:["#5e8a4a","#2a3319"],
    courses:[
      {t:"Saying What You Mean", m:"Intent articulation as a trainable skill"},
      {t:"Reading the Output You Got", m:"Verification instinct; resisting fluency-as-correctness"},
      {t:"The Lines You Don't Cross", m:"Data handling, confidentiality, prohibited uses"},
      {t:"Knowing What It Can't Do", m:"Capability boundaries and honest limits"},
      {t:"Working Faster Without Working Sloppier", m:"Task selection — what to hand over, what to keep"},
    ]
  },
  {
    id:"caie", badge:"assets/img/badge-caie.png", code:"CordiaCAIE", name:"Certified AI Employee",
    who:"Practitioners who design and deploy AI workflows in their own function.",
    claim:"This person can specify a workflow well enough that someone else could verify it, and knows when to stop it.",
    mix:"~65% free text, 15% selected, 20% hybrid",
    signature:"The reproduction test — your specification is attempted by a second learner. Your score is partly their success rate. Cohen's κ operationalized as an exam item.",
    cut:"Can they produce a specification that works in someone else's hands?",
    g:["#8fb573","#3d4a2a"],
    courses:[
      {t:"Specification That Survives Independent Reading", m:"Writing intent someone else can score — the κ skill"},
      {t:"Success Criteria Before You Start", m:"Defining 'good' from the receiver's viewpoint"},
      {t:"Model and Tool Routing", m:"Ambiguity × consequence; underspecification as the real signal"},
      {t:"Building the Workflow", m:"Practical construction — n8n, connectors, context, skills"},
      {t:"Failure Design", m:"What breaks, what stops it, what happens while waiting"},
      {t:"Measuring Whether It Worked", m:"Outcome, quality, and integrity metrics; cost-per-task"},
    ]
  },
  {
    id:"caaie", badge:"assets/img/badge-caaie.png", code:"CordiaCAAIE", name:"Certified Advanced AI Employee",
    who:"People accountable for agent systems others depend on. Maps to EU AI Act Article 26 human-oversight competence.",
    claim:"This person can hold accountability for a system they did not personally execute, and can prove what it did.",
    mix:"~70% free text, 10% selected, 20% hybrid",
    signature:"Two signature items: (1) longitudinal drift — your d′ trajectory reviewing seeded outputs across weeks, nobody can cram for it. (2) The accountability interview — 'An auditor asks why your system produced this output. Answer them.'",
    cut:"Would you accept this person as the named accountable owner under Canvas S31? That's the standard Article 26 effectively imposes.",
    g:["#a08a3c","#6e5c28"],
    courses:[
      {t:"Designing the System That Runs Without You", m:"Full six-layer canvas: source through sharpen"},
      {t:"Decision Rights and Where Authority Stops", m:"Autonomous / recommends / escalates — mapped explicitly"},
      {t:"The Autonomy Dial", m:"Capability × criticality; scheduled review"},
      {t:"Detecting Your Own Drift", m:"Automation bias, alert fatigue, normalization of deviance"},
      {t:"Proving What Happened", m:"Decision logs, explainability, audit readiness"},
      {t:"Governing a Hybrid Team", m:"Accountability when the worker is not a person"},
    ]
  }
];
