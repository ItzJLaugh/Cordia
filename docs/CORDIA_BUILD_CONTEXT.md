# Cordia — Canonical Product & Build Context

Last updated: 2026-08-14

> Purpose
>
> This document is the stable product truth and north-star architecture for engineers and coding agents working on Cordia. Read this entire document before changing architecture, UX, workspace behavior, Surveyor logic, assessment logic, connector behavior, agent runtime behavior, desktop deployment, or browser-assisted setup.
>
> Do not infer Cordia from older descriptions such as “AI coding language,” “course platform,” “generic agent builder,” or “node graph editor.” Those are pieces or historical phases of the system, not the current product definition.

---

# 1. Core Product Definition

Cordia is building an **agentic Forward Deployed Engineer for the individual**.

Traditional Forward Deployed Engineers study an organization’s workflows, integrate systems, build tooling, and adapt software to the organization’s operating environment. Cordia performs that function for **one person**.

The intended experience is:

> Cordia learns how you work, understands the systems you use, and builds a personalized agentic working environment around you — ideally in less than an hour.

Cordia integrates AI **for the person**, not for an entire company.

The individual should not have to understand:

- agent orchestration
- MCP implementation
- API structure
- OAuth internals
- tool schemas
- workflow graphs
- model routing
- prompt engineering internals
- browser automation internals
- CLI integration
- local agent bridges
- secret storage
- software architecture

Cordia performs that technical translation.

A concise market framing is:

> **Cordia is a personal agentic Forward Deployed Engineer.**

Supporting explanation:

> Cordia learns how you work, connects the systems you already use, and builds a personalized AI operating environment around your intent.

A future market promise, once validated, may be:

> A personal AI integration that can begin taking shape in under an hour.

Do not overstate implementation speed for unsupported connectors.

---

# 2. Fundamental Product Principle

Most AI systems require the human to adapt to the software.

Cordia should adapt the software to the human.

The product loop is:

```text
MEASURE
   ↓
LEARN
   ↓
CERTIFY
   ↓
BUILD
   ↓
RUN
   ↓
OBSERVE INTENT GAPS
   ↓
REFINE
   ↺
```

These are not separate products. They are different surfaces of one system.

Cordia should not ask users to navigate unnecessary product complexity. Cordia should route them.

Every major screen should answer one of these questions:

- What is Cordia measuring?
- What is Cordia teaching?
- What is Cordia certifying?
- What is Cordia building?
- What is Cordia running?
- What did the AI miss?

---

# 3. Core HCI Question

The key HCI question is:

> **How can the human express intent at a resolution an AI system can act on without forcing the human to perform the translation themselves?**

Every major UX decision should be evaluated against that question.

Prefer:

```text
user asks
→ Cordia interprets
→ Cordia proposes
→ user approves if needed
```

over:

```text
open settings
→ open connector
→ choose API
→ configure scope
→ choose tool
→ create agent
→ connect nodes
→ define workflow
→ save
```

Configuration screens should mostly support:

- inspection
- override
- debugging
- advanced control

The primary interaction should be conversational wherever practical.

---

# 4. Surveyor

The Surveyor is the first meaningful interaction for a new user.

It must be a **natural conversational AI agent**, not a static form.

Never replace the Surveyor’s primary assessment experience with:

- multi-page questionnaires
- dropdown-heavy onboarding
- personality-test forms
- keyword matching
- rigid semantic field collection

The user should feel like they are simply talking to Cordia.

Example:

```text
Surveyor:
What kind of work are you trying to make easier with AI right now?

User:
I review building enclosures and write reports based on field observations.

Surveyor:
When an AI gives you something that looks correct but feels incomplete,
what do you usually notice first?

User:
Usually the missing connection between the field condition and why it
actually matters.
```

Surveyor should adaptively investigate areas such as:

- domain / type of work
- actual recurring work
- work goals
- role tendency
- situational reasoning
- visual vs verbal working preference
- graph/system-map preference
- drawing/sketching preference
- detail orientation
- gap detection
- constraint setting
- verification behavior
- uncertainty handling
- risk boundaries
- delegation comfort
- human checkpoint preference
- communication style
- tool-selection behavior
- workflow decomposition
- learning preference
- existing applications and systems
- APIs/connectors likely needed
- where AI commonly misses the user’s intent

Do not ask every user every question. Ask what is necessary to resolve missing signals.

---

# 5. Surveyor Reasoning Model

Do **not** primarily use shallow keyword rules such as:

```text
user says “graphs”
→ graph_preference = high
```

The intended flow is:

```text
user answers naturally
      ↓
answers accumulate into evidence
      ↓
answers are evaluated in batches
      ↓
evaluator correlates evidence against hidden criteria
      ↓
criteria receive:
    - value/score
    - confidence
    - evidence
      ↓
system determines which signals remain unresolved
      ↓
Surveyor asks next useful question
```

The profile is a **working hypothesis**, not a permanent psychological truth.

Use explicit evidence and confidence.

Do not claim Cordia perfectly understands a user’s personality.

Potential hidden criteria include:

```text
intent_clarity
gap_detection
constraint_setting
risk_boundary_awareness
delegation_readiness
visual_systems_thinking
verification_instinct
domain_specificity
workflow_decomposition
human_checkpoint_judgment
```

The exact criterion model may evolve.

Important requirements:

- criteria must be inspectable
- inference should contain evidence
- confidence should be stored
- complex ML is not required for MVP
- simple rubric-driven LLM evaluation is preferred initially
- user need not see raw hidden scores

---

# 6. Survey Assessment

The Surveyor assessment is **not a scored exam**.

The UI must not present:

- overall score
- percentile
- pass/fail
- rank
- “questions answered”
- test-style grading

Instead, “View my assessment” should mean:

> **What Cordia currently understands about how I think, work, and interact with AI.**

Suggested sections:

## What we know

- Domain & work focus
- Role tendency
- Thinking / working style
- Visual systems preference
- Gap-detection style
- Risk & delegation behavior
- Communication preferences
- Existing tools/applications

## Profile signals

Examples:

```text
Visual systems thinking       High
Analytical depth              High
Detail orientation            High
Risk awareness                Medium
Delegation comfort            Medium
Creative exploration          Emerging
Verbal preference             Medium
```

These are not exam scores. They are interpreted profile signals.

## Evidence

Show short conversational evidence:

```text
“Visuals and system maps help me think and understand complex problems.”

“I usually catch what is missing or what doesn’t connect to the real issue.”

“Before anything client-facing, I want to review and approve it.”
```

## Still learning

Examples:

- constraint setting
- delegation comfort
- tool selection
- learning style

The user should always be able to reopen Surveyor and refine the profile.

---

# 7. Markdown Artifact Layer

Surveyor should not directly create the final workspace.

Surveyor creates source documents that Cordia can compile into an actionable workspace plan.

Core artifacts:

```text
operator.md
connectors.md
intent-misses.md
        ↓ compiled into
fde-tasks.md
permissions.md
workspace-plan.md
```

Recommended distinction:

```text
operator.md
    Who the user is as an operator.

connectors.md
    What systems, apps, APIs, MCPs, and local tools the user uses or should connect.

intent-misses.md
    Where Cordia or other AI systems previously misunderstood the user.

fde-tasks.md
    The compiled mission brief for what Cordia should do for this person.

permissions.md
    What the Cordia agent can do, must ask before doing, or cannot do.

workspace-plan.md
    The proposed visual workspace, windows, connectors, skills, context, and automations.
```

The clean mental model is:

```text
operator.md = who I am
connectors.md = what I use
intent-misses.md = how AI has failed me
fde-tasks.md = what Cordia should do about it
permissions.md = what Cordia is allowed to do
workspace-plan.md = what Cordia should build visually
```

---

# 8. fde-tasks.md as Compiled Mission Brief

`fde-tasks.md` is not simply a list of tasks.

It is the **living mission brief for the personal FDE**.

It should be compiled from:

```text
operator.md
+
connectors.md
+
intent-misses.md
+
current workspace goals
```

But `operator.md` and `connectors.md` should remain separate source files.

Reason:

- `operator.md` = user/person/context facts
- `connectors.md` = available systems and access paths
- `intent-misses.md` = raw/structured history of missed intent
- `fde-tasks.md` = actionable interpretation of all of that

Do not permanently dump everything into `fde-tasks.md`.

A useful storage distinction is:

```text
/source/operator.md
/source/connectors.md
/source/intent-misses.md
        ↓ compile
/runtime/fde-tasks.md
```

`fde-tasks.md` should become workspace-specific mission context injected into the Cordia agent prompt.

It should not be the entire system prompt.

Preferred layering:

```text
global Cordia system prompt
+
Cordia safety rules
+
workspace permissions
+
compiled fde-tasks.md
+
current workspace state
+
current user message
```

---

# 9. Intent-Miss Memory

Intent misses are central to the product.

When the user says the AI missed what they meant, Cordia should not just regenerate.

Cordia should record structured memory.

Example:

```md
## Intent Miss: 2026-08-12

User asked:
“Give me actual code, not another framework.”

Cordia did:
Returned high-level architecture guidance and partial pseudocode.

Miss type:
- too abstract
- not implementation-ready
- ignored requested specificity

Correction:
When the user asks for code, provide complete runnable files or clearly state what cannot be completed.

Effect on FDE tasks:
Increase preference for concrete implementation, file paths, diffs, and executable steps during build sessions.
```

For MVP, avoid overengineering hidden numerical scoring.

Start with:

```text
low / medium / high
+
evidence
+
last updated
```

Later, scoring can evolve into values such as:

```yaml
implementation_specificity:
  value: 0.88
  confidence: 0.74
  evidence:
    - “User repeatedly asked for actual code rather than frameworks.”
```

The MVP should keep this simple and inspectable.

Raw memory can contain detailed events/transcripts. Compiled memory should remain concise and operational.

---

# 10. Workspace Builder

The workspace builder is where Cordia’s FDE premise becomes real.

The user should **not** be expected to build an agent graph manually.

Cordia should generate an initial workspace based on:

- Surveyor profile
- work domain
- desired outcomes
- connectors
- existing tools
- required permissions
- available skills
- context sources
- intent-miss history

The user primarily builds by talking to the Cordia agent.

Example:

```text
Cordia:
Based on your Surveyor profile, I started with a visual research workspace.
You prefer system views and human approval before consequential outputs.

What would you like this workspace to help you do?

User:
Pull together research, compare it, and let me approve anything before
it gets sent.

Cordia:
I’ll configure that now.
```

The visual workspace updates as the conversation occurs.

---

# 11. Workspace Is Both Builder and Runtime

Do not create a hard conceptual divide between:

```text
builder
finished workspace
```

The workspace builder becomes the workspace.

Building and using are the same mode.

The Cordia agent remains embedded after initial configuration.

The user can keep modifying the workspace after it is live.

This applies to both the Cordia Web App and Cordia Desktop App.

---

# 11A. Alidora — Agentic System Builder by Cordia

Alidora is Cordia's advanced system-building surface. It makes the technical structure behind an AI-enabled workspace understandable and operable for users who need to build a company-level agentic system: agent roles, workflows, runs, approvals, dependencies, and system health.

```text
Cordia
    Personal FDE, conversational workspace, connectors, permissions, outcomes

Alidora by Cordia
    Advanced Agentic System Builder: compose, inspect, and operate agent systems
```

Alidora is a first-class Cordia tab/module, not a separate application and not the default first-run experience. Cordia should route users into it when their work calls for explicit system design, workflow inspection, or advanced operational control.

Both surfaces share Surveyor/profile/evidence, source and compiled FDE artifacts, canonical workspace state, the connector and capability registry, ALLOW / ASK / DENY enforcement, approvals, audit, and outcome memory.

Alidora may provide a graph canvas, workflow/agent composition, run history, traces, approval checkpoints, and reusable company agent systems. It must not introduce a second connector catalog, state store, permission engine, execution gateway, secret path, or outcome-learning loop. Its graph must describe and mutate canonical state through typed Cordia contracts; it must never become hidden competing state.

---

# 12. Workspace UI

Desktop target:

```text
┌───────────────────────────────────────────────────────────────┐
│ cordia                My Workspace                     Run    │
├───────────────┬───────────────────────────────────────────────┤
│               │                                               │
│ CORDIA AGENT  │            WORKSPACE SURFACE                  │
│               │                                               │
│ conversation  │   Drive       Discord      Claude Code        │
│ from top      │                                               │
│ to bottom     │   Hostinger   Mercury      Notion             │
│               │                                               │
│ config chats  │   Brave       CordiaCode   Derived View       │
│               │                                               │
├───────────────┴───────────────────────────────────────────────┤
│ Connected │ Skills │ Access │ Context │ Automations │ Activity │
└───────────────────────────────────────────────────────────────┘
```

The Cordia assistant should occupy the **left side from top to bottom**.

It should not be visually separated from the workspace as if it were another application.

It is the FDE controlling and configuring the environment.

The right side is the live visual workspace.

The bottom strip is for inspection/control, not primary configuration.

---

# 13. Visual Workspace Windows

The main workspace should contain real visual surfaces representing the user’s connected systems.

Examples:

- Google Drive
- Discord
- Claude Code
- Brave Search
- Hostinger
- Mercury
- Notion
- CordiaCode
- GitHub
- Gmail
- Calendar
- local repo
- terminal
- local scripts

Do not connect windows with arbitrary node-graph edges.

This is not primarily a topology editor.

The user should feel that their applications have been brought together into one personalized operating environment.

---

# 14. Native Connector Views, Not Website Embeds

Do not rely on iframing entire third-party websites.

Preferred architecture:

```text
connector/API/MCP/local tool
        ↓
data/capability
        ↓
Cordia-native window renderer
```

A Google Drive window should not be the full Google Drive website.

It should be a Cordia-native view of useful Drive data:

```text
Google Drive
Project Files
Recent Docs
Shared Sources
Needs Review
```

The window can resemble the familiar application enough to orient the user, but it should be rendered by Cordia.

Reasons:

- iframe restrictions
- CSP / X-Frame-Options
- auth complexity
- inconsistent UX
- derived Cordia views do not exist in the source application

---

# 15. Derived Windows

A window does not need to map directly to one app.

Cordia can create derived task windows from multiple connectors.

Example:

User says:

> Tell me if anything engineering says in Discord changes the product roadmap.

Cordia combines:

```text
Discord
+
Notion
+
comparison skill
```

and creates:

```text
ROADMAP IMPACT

3 engineering updates detected.
1 affects roadmap.

Authentication API delayed
→ affects Beta Launch

[Review]
```

This is a critical product insight.

Cordia should not merely recreate app dashboards.

Cordia should create windows that make the user’s work easier.

---

# 16. Capability Hierarchy

Use this hierarchy:

```text
Connector
    Provides access to a system.

Tool
    One primitive operation.

Script
    Deterministic procedure made of tools.

Skill
    Human-level capability Cordia can reason about.
```

Examples:

## Connector

```text
Google Drive
Discord
Notion
Mercury
Claude Code
Brave Search
Hostinger
GitHub
CordiaCode
```

## Tool

```text
drive.list_files
drive.read_file
discord.read_messages
discord.send_message
brave.search
mercury.list_transactions
hostinger.deploy_preview
```

## Script

```text
collect_weekly_project_context
    1. read Drive project folder
    2. read Discord project channel
    3. read Notion roadmap
    4. normalize data
    5. return context object
```

## Skill

```text
Compare research
Prepare weekly project review
Summarize client materials
Review financial activity
Deploy preview
Draft client update
```

The agent decides what skill is needed.

The skill/script/tool system determines how it is executed.

Do not define every click as a skill.

Bad:

```text
click_file
open_folder
press_download
click_search
```

Good:

```text
find_project_documents
compare_sources
prepare_client_update
summarize_research
review_recent_transactions
publish_preview
```

---

# 17. MCP Server Role

Important correction:

The MCP server is **not** the dashboard.

The dashboard/workspace UI is what the human sees.

The Cordia agent is the reasoning client/orchestrator.

The Cordia MCP server is the unified capability gateway.

Correct model:

```text
Dashboard / Workspace UI = human-facing interface
Cordia Agent = reasoning client/orchestrator
Cordia MCP Server = capability gateway/router
Connectors/APIs/apps/local tools = systems behind the gateway
```

There are effectively two clients:

```text
Human-facing client:
    Cordia dashboard / desktop UI

Tool-facing client:
    Cordia agent runtime

Server:
    Cordia MCP server / capability gateway
```

Loop:

```text
User
  ↓
Dashboard UI
  ↓
Cordia Agent
  ↓
Cordia MCP Server
  ↓
Connector/API/local tool
  ↓
Cordia MCP Server
  ↓
Cordia Agent
  ↓
Workspace State
  ↓
Dashboard UI
  ↓
User sees updated window
```

---

# 18. Unified Capability Gateway

The goal is that the Cordia agent should only need to talk to one capability gateway.

The agent should not need to know technical setup details for every service.

Conceptually:

```text
Every connector becomes a capability exposed through the Cordia MCP server.
The Cordia agent calls Cordia MCP tools.
The MCP server handles the real implementation path behind the scenes.
```

The agent sees tools like:

```text
drive.search_files
discord.read_channel
hostinger.deploy_preview
mercury.list_transactions
brave.search
claude_code.run_task
```

The MCP server handles whether that requires:

- OAuth
- API key
- REST call
- curl command
- Lightpanda browser setup
- local CLI
- desktop bridge
- local script
- external MCP server

---

# 19. Lightpanda / Browser Setup Strategy

A major product idea is that most users do not know how to get an API key or configure developer access.

Cordia should remove these setup hops.

Use Lightpanda or another agent browser as a **setup assistant**.

Important distinction:

```text
Lightpanda / browser agent = setup assistant
curl/API/MCP = durable runtime
Cordia agent = orchestration client
Cordia MCP server = capability gateway
```

Cordia should use the browser only long enough to turn a human-only setup path into a durable connector.

After setup, runtime should use direct API/MCP/curl-style calls whenever possible.

---

# 20. Guided API-Key Setup

Target user experience:

```text
User:
Connect Hostinger.

Cordia:
I can set that up for you.
I’ll open a secure browser session and walk you to the API token page.
You only need to sign in and click Generate when I stop.

[Start secure setup]
```

Flow:

```text
Cordia Browser Setup
        ↓
Open provider site
        ↓
Navigate login
        ↓
User enters password / 2FA manually
        ↓
Cordia navigates to API settings
        ↓
Cordia pauses at token creation
        ↓
User clicks Generate API Key
        ↓
Token is captured into sealed setup environment
        ↓
Token is stored in encrypted vault
        ↓
Cordia tests connector with curl/API call
        ↓
Connector becomes live
        ↓
Browser session is destroyed
```

This removes the normal burden:

```text
Go to settings
Find developer/API page
Generate token
Copy token
Return to Cordia
Paste token
Choose scopes
Test connection
Debug errors
```

Cordia handles navigation and validation.

The user handles sensitive identity actions.

---

# 21. Credential Boundary

Do not design Cordia so the user gives their password to the agent.

Better model:

```text
Cordia may fill email if user approves.
User types password directly into browser.
User completes 2FA directly.
Cordia cannot read password field value.
Cordia cannot store password.
Cordia only continues after authentication succeeds.
```

Human credential boundary:

```text
Agent can navigate.
Agent can explain.
Agent can click safe setup pages.
Agent can pause.
User enters password / 2FA.
Agent cannot see password.
Agent cannot export password.
```

This is crucial for trust.

---

# 22. Secret Handling

Raw API keys should not be given to the LLM as ordinary text.

Preferred flow:

```text
API token appears in browser
        ↓
Cordia setup capture layer detects token field
        ↓
Token is sent directly to encrypted secret vault
        ↓
Agent receives only:
    “Hostinger token saved and validated”
```

The agent should receive a handle:

```json
{
  "secret_ref": "secret_hostinger_api_key_7f31",
  "connector_id": "hostinger",
  "status": "validated"
}
```

not the raw key.

Future tools use the `secret_ref`.

Example:

```text
Cordia Agent
   ↓ calls
hostinger.deploy_preview(secret_ref)
   ↓
Cordia MCP Server retrieves token securely
   ↓
Hostinger API
```

---

# 23. Enclosed Setup Environment

For guided browser setup, use three boundaries.

## Browser sandbox

```text
ephemeral cookies
ephemeral browser profile
no persistent password access
record only approved setup trace
destroy session after setup
```

## Secret boundary

```text
browser token field
    → secure capture
    → vault
    → secret_ref
```

The LLM/agent should never have raw token text in prompt context.

## Tool boundary

The agent should call typed tools through MCP.

Good:

```text
hostinger.deploy_preview(site_id)
```

Bad:

```text
curl arbitrary internet URL with this token
```

---

# 24. Connector Manifest Setup Strategy

Each connector should define how setup works.

Example:

```yaml
id: hostinger
display_name: Hostinger

setup:
  strategy: guided_browser_api_key
  browser_engine: lightpanda
  start_url: https://hpanel.hostinger.com
  user_auth_required: true
  credential_policy:
    password_visible_to_agent: false
    user_enters_password: true
    allow_agent_fill_email: true
  target:
    description: Navigate to API token creation
    pause_before_token_generation: true
    user_click_required: true
  secret_capture:
    type: api_key
    destination: vault
    expose_to_agent: false

runtime:
  preferred: direct_api
  fallback: browser
  tools:
    - hostinger.list_sites
    - hostinger.deploy_preview
    - hostinger.read_dns
```

This allows Cordia to understand:

```text
This connector is set up through guided browser.
After setup, it runs through direct API calls.
```

---

# 25. Browser for Setup, API/curl for Runtime

Use browser automation for:

```text
login flows
API-key creation flows
OAuth-ish setup pages
sites without clean APIs
one-time connector setup
workflow discovery
user-guided browser tasks
fallback when direct API path fails
```

Use direct API / curl / MCP tools for:

```text
normal connector runtime
repeatable actions
status checks
file reads
message reads
deploy calls
search calls
data sync
automations
```

Do not use browser automation forever if a durable API path exists.

---

# 26. Permissions

Permissions primarily describe what the Cordia agent is allowed to do inside the workspace.

They are not primarily multi-user workspace roles.

User-facing model:

## Cordia can

```text
✓ Read project files
✓ Search the web
✓ Analyze financial information
✓ Execute local code
✓ Update Notion
```

## Cordia must ask before

```text
? Sending messages
? Publishing code
? Deleting files
? Editing consequential external records
? Deploying production
```

## Cordia cannot

```text
✕ Transfer money
✕ Change security settings
✕ Add administrators
```

Recommended permission states:

```text
ALLOW
ASK
DENY
```

High-risk operations should support future HITL pause/resume.

Permissions must be enforced before tool execution, not merely displayed in UI.

---

# 27. Context

Context should mostly be collected automatically.

Do not force users to configure a complicated context system.

Instead, show something like:

```text
CORDIA CURRENTLY KNOWS FROM

Google Drive        142 files
Discord             3 channels
Notion              18 pages
Mercury             90 days
Surveyor            profile active
Workspace history   27 runs
```

Allow users to inspect or disable individual sources.

Context is primarily an inspection/control surface, not an onboarding form.

---

# 28. Plugins / APIs / MCP Terminology

Avoid forcing non-technical users to understand distinctions among:

```text
Connector
API
MCP
Plugin
Script
Tool
```

Those are engineering concepts.

The user should primarily see:

## Connected systems

```text
Drive
Discord
Notion
Mercury
Claude Code
```

## Cordia can

```text
Research
Summarize
Compare
Write
Code
Deploy
Analyze
Message
```

## Cordia access

```text
Read files        Allow
Send messages     Ask
Execute code      Allow
Deploy            Ask
Move money        Never
```

Technical configuration can remain available through progressive disclosure.

---

# 29. Canonical Workspace State

The workspace should have one canonical state representation.

Conceptually:

```text
Workspace
├── windows
├── connectors
├── skills
├── agents
├── permissions
├── context sources
├── automations
├── mutations
├── execution/runtime state
├── provenance
└── desktop/local capability status
```

Both the human and the Cordia agent should mutate the **same canonical workspace state**.

Do not create independent “AI-generated layout state” and “user layout state.”

---

# 30. Mutations and Provenance

Every meaningful change should be attributable.

Example:

```yaml
actor: cordia
operation: add
target: connector
target_id: hostinger
summary: Added Hostinger connector as guided API-key setup
provenance:
  source: fde-tasks.md
  evidence: User said they host CordiaCode on Hostinger
timestamp: 2026-08-12T13:00:00-05:00
```

This supports:

- undo
- audit trail
- user trust
- debugging
- explanation
- workspace evolution
- future local/cloud sync

---

# 31. Connector Lifecycle

Recommended connector states:

```text
PROPOSED
IN_PROGRESS
LIVE
FAILED
DECLINED
NEEDS_HANDOFF
```

The UI should reflect these states naturally.

Example proposed:

```text
Google Drive
Suggested because you rely on source documents.

[Connect]
```

In progress:

```text
Google Drive
Connecting...
```

Needs handoff:

```text
Hostinger

One thing I need from you.

1. Sign in.
2. Click Generate API Key.
3. I will test it and finish setup.
```

Live:

Actual Cordia-native connector window appears.

Failure in one connector should not break the entire workspace.

---

# 32. Web App vs Desktop App

Cordia has two main surfaces.

## Cordia Web App

Used to:

```text
sign up
complete Surveyor
view assessment
build first workspace
connect cloud apps
save workspace
download install.ps1
```

## Cordia Desktop App

Used to:

```text
run the same workspace locally
keep Cordia agent embedded
access local files/tools/repos/scripts
use Claude Code/local development tools
keep modifying the workspace
```

They share the same cloud workspace state.

The desktop app should feel like:

> **Take the workspace I built in Cordia and install it as my local AI operating environment.**

---

# 33. install.ps1 Flow

Critical correction:

`install.ps1` is **not** part of initial workspace creation.

It is the desktop deployment/install step **after the user has already built and saved a workspace in the Cordia web app**.

Flow:

```text
User clicks “Install Cordia Desktop”
        ↓
Cordia downloads install.ps1
        ↓
User runs install.ps1
        ↓
Cordia Desktop App installs
        ↓
User opens desktop app
        ↓
User signs in with same email
        ↓
Desktop app pulls saved workspace from Cordia Cloud
        ↓
Desktop registers local device
        ↓
Desktop enables local bridge
        ↓
Local capabilities sync back to workspace
        ↓
Same workspace now runs locally
```

Before desktop install:

```text
Cloud:
✓ Drive
✓ Discord
✓ Notion
✓ Brave Search
✓ Hostinger
✓ Mercury
```

After desktop install:

```text
Cloud:
✓ Drive
✓ Discord
✓ Notion
✓ Brave Search
✓ Hostinger
✓ Mercury

Local:
✓ Claude Code
✓ Local repo
✓ PowerShell
✓ Python scripts
✓ Docker
✓ VS Code project
```

---

# 34. Desktop Local Bridge

The desktop app should provide a local bridge for tools the cloud web app cannot safely access.

Examples:

```text
Claude Code
local repo
local filesystem
PowerShell scripts
Python scripts
Docker
VS Code workspace
terminal commands
local MCP servers
private dev environment
```

The local bridge should still enforce permissions.

Example:

```text
Read local project files         Allow
Write local project files        Ask
Run tests                        Allow
Run arbitrary shell command      Ask
Install packages                 Ask
Push to GitHub                   Ask
Deploy production                Deny by default
Read personal folders            Deny by default
```

---

# 35. LangGraph / LangChain

LangGraph is a strong candidate for the underlying agent runtime.

However:

> Cordia must own the product state and product contracts.

Do not make LangGraph itself the Cordia architecture.

Preferred layering:

```text
Cordia UI
Surveyor
Profile
Workspace state
Skill registry
Permissions
        ↓
Cordia Runtime Contract
        ↓
LangGraph adapter
        ↓
models / tools / MCP
```

LangGraph may eventually handle:

- durable workflow execution
- pause/resume
- branching
- tool routing
- human approvals
- checkpoints
- recovery

But it should remain replaceable.

---

# 36. Intent Gap Layer

Long-term Cordia behavior should support structured feedback when an AI output fails to match human intent.

Instead of only:

```text
Regenerate
👍
👎
```

Cordia should allow signals such as:

```text
Missing context
Wrong audience
Too generic
Needs evidence
Wrong format
Wrong constraint
Unsafe to automate
Needs human checkpoint
```

These signals can feed:

- profile refinement
- runtime routing
- agent selection
- course recommendation
- future model improvement
- `intent-misses.md`
- recompilation of `fde-tasks.md`

---

# 37. Visual Theme

Current Cordia design language:

- warm ivory / soft white
- dark olive green
- generous whitespace
- very light borders
- subtle floating shadows
- minimal gradients
- lowercase `cordia`
- Cordia infinity/loop icon with small pixel fragments
- small leaf used as the dot of the `i`
- formal serif used selectively for editorial headings
- clean sans-serif for product UI
- mono typography for technical/system information

The product should feel:

```text
modern technology
+
research laboratory
+
environmental intelligence
+
human calm
```

Not:

```text
AI neon cyberpunk
enterprise dashboard overload
generic SaaS startup
gamified learning product
```

The workspace should feel cleaner than the early mockups, with fewer visible technical controls and more direct app/task surfaces.

---

# 38. Brand Meaning

Cordia comes from tropical flowers and carries themes of:

- life
- freedom
- environmental respect
- human fulfillment
- technology reducing unnecessary labor

The product vision is not simply:

> automate more work.

It is closer to:

> reduce unnecessary technical labor so humans can spend more time doing work that matches their interests, cognition, creativity, relationships, and lives.

Avoid exaggerated promises in production claims unless validated.

---

# 39. Engineering Philosophy

Keep the architecture:

- simple
- inspectable
- modular
- explicit
- easy to extend
- resistant to hidden model behavior

Prefer:

- explicit schemas
- manifests
- rule-based safety
- validated LLM output
- capability boundaries
- least privilege
- readable sequential logic

Avoid premature:

- complex ML personalization
- embedding-heavy profile systems
- autonomous self-modifying architecture
- opaque permissions
- excessive microservices

---

# 40. Personalization Kill Switch

Complex personalization must always be removable.

Conceptual modes:

```text
off
simple
adaptive
```

`simple` should remain viable permanently.

If adaptive logic becomes fragile, the product must still work using:

- explicit user profile
- Surveyor evidence
- simple heuristics
- user-selected preferences

---

# 41. Current Priority

The highest-value product sequence is:

```text
Surveyor
   ↓
profile assessment
   ↓
generated workspace
   ↓
connect real systems
   ↓
skills/capabilities appear
   ↓
Cordia configures environment through chat
   ↓
user performs real work
   ↓
intent-gap feedback
   ↓
workspace/profile refinement
   ↓
optional desktop installation of the saved workspace
```

The current engineering effort should prioritize making this vertical slice **real**.

After the smallest Cordia vertical slice is reliable, the next expansion is Alidora's read-only Workspace Map/System View over canonical workspace state. Authoring and execution features follow only after their shared state, capability, permission, and audit contracts are proven.

---

# 42. North-Star User Experience

A new user should eventually be able to experience:

```text
0:00
Sign in.

0:01
Surveyor starts talking naturally.

0:10
Cordia understands the person’s domain, work patterns,
preferred interface, risk boundaries, and major tools.

0:15
User views an inspectable Surveyor assessment.

0:20
Cordia proposes a workspace.

0:25
Drive, Notion, Discord, code environment, finance system,
search, and other useful systems begin connecting.

0:35
The workspace visually becomes the person’s actual work environment.

0:40
Cordia explains what it can do and what requires approval.

0:45+
The person begins doing real work through Cordia.

Later:
User clicks “Install Cordia Desktop,” signs in locally, and loads the same workspace with local capabilities enabled.
```

Exact timing is aspirational until empirically validated.

The essential idea is not the time.

The essential idea is:

> **AI integration becomes a personal conversation instead of an engineering project.**

---

# 43. Before Coding

Before changing implementation:

1. Inspect the existing repository.
2. Identify what already exists.
3. Reuse current contracts where sound.
4. Do not create a second parallel architecture.
5. Map existing implementation to this canonical model.
6. Call out conflicts explicitly.
7. Prefer migration/refactoring over replacement where practical.
8. Build a smallest real vertical slice before expanding connector coverage.
9. When reviewing parallel implementations, use component-level evidence to choose **adopt**, **adapt**, **compose**, or **reject**. Do not blindly merge a whole feature stack because it is sophisticated.
10. Preserve one owner for each cross-cutting concern: workspace state, connector/capability registry, permission/approval enforcement, execution gateway, secrets, and outcomes.

Repository:

```text
ItzJLaugh/Cordia
```

Default branch:

```text
main
```

---

# 44. Final North-Star Architecture

```text
Surveyor creates understanding.
Markdown artifacts preserve understanding.
fde-tasks.md compiles the mission.
Workspace builder turns mission into interface.
Canonical workspace state is the source of truth.
Cordia Agent reasons over mission, permissions, current state, and current user message.
Cordia MCP Server exposes unified capabilities.
Browser automation removes setup hops.
Direct API/curl/MCP becomes durable runtime where possible.
Cordia Web App builds and saves the workspace.
install.ps1 installs the saved workspace as Cordia Desktop after build.
Cordia Desktop adds local capabilities through a local bridge.
Intent misses update memory and recompile the FDE mission.
The workspace continuously improves.
```
