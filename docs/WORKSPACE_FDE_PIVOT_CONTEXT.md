# Cordia Workspace / FDE Pivot Context

Last updated: 2026-08-12

This document preserves the detailed context that began with the question:

> “This file contains numerous artifacts into the system and logic behind cordia creating a workspace - starting from the survey to final implementation. Realistically, could this be built to match exactly the UI image you created?”

It captures the resulting architectural discussion, later pivots, corrections, and implementation direction. This is intentionally detailed. A coding agent should treat this as product context to reconcile with the current codebase, not as a blind instruction to rewrite existing code.

---

# 1. Reality Check: The Existing Artifact Model Can Support the UI

The uploaded workspace artifacts already described concepts that map well to the desired interface:

- workspaces
- windows
- connectors
- agents
- mutations
- autonomy
- provenance
- provision state
- execution route

A key realization was that the workspace UI does not need a separate invented representation. The frontend can render from the workspace state directly.

Conceptually:

```text
Surveyor / operator understanding
        ↓
Interpreter reading
        ↓
Validated connector picks
        ↓
Workspace spec
        ↓
Window[] + ConnectorBinding[] + AgentBinding[]
        ↓
Frontend renders the actual workspace
```

A visual workspace window should be backed by something real:

```text
connector
agent
local source
skill/derived view
```

with a layout position such as:

```text
x
y
w
h
```

This means the workspace can be represented declaratively and rendered dynamically.

---

# 2. Do Not Iframe Whole Applications

The early visual idea showed windows resembling Google Drive, Discord, Notion, Mercury, Hostinger, etc.

The correct implementation should **not** be eight websites embedded in iframes.

Instead:

```text
Google Drive connector
        ↓
Drive API / MCP
        ↓
recent/project file data
        ↓
Cordia DriveWindow component
```

The component may visually resemble the familiar application, but it is Cordia-native and backed by real connector data.

This matters because:

- many services block iframe embedding
- auth becomes messy with iframes
- UX becomes inconsistent
- Cordia needs to create views the source application does not have
- Cordia should become the operating surface, not a browser tab container

---

# 3. Native Connector Windows

A Google Drive window might show:

```text
My Drive
Shared
Recent

Project Plan.pdf
Research Notes.docx
Budget.xlsx
```

A Discord window might show:

```text
Research
Announcements
Engineering
Mentions
```

A Notion window might show:

```text
Product Roadmap
Open Tasks
Research Notes
Decision Log
```

A Mercury window might show:

```text
Cash position
Recent expenses
Runway
Transactions requiring review
```

The goal is not to fully reproduce each product.

The goal is to expose the part of each product useful for the operator’s work.

---

# 4. The Bigger Pivot: Windows Should Become Task Surfaces

The concept became stronger when the workspace stopped being viewed as a collection of miniature applications and instead became a collection of **useful task surfaces**.

Connector-native mode is useful when familiarity matters.

Example:

```text
Google Drive
My Drive | Shared | Recent
Research/
Launch/
Contracts/
```

But Cordia should also create task-specific derived views:

```text
CLIENT MATERIAL

Needs review                 3
Updated this week            8
Referenced in active work   14
Missing source               2
```

That view may be powered by Drive but does not exist inside Drive.

This is where Cordia becomes an FDE rather than a portal.

A human FDE would not merely say “Here is your Google Drive.” They would say, “You keep needing these seven documents to approve client deliverables, so I made you a view containing them.”

---

# 5. Derived Multi-Connector Windows

A window can be built from multiple connectors and skills.

Example user request:

> “I want to know every morning if engineering said something in Discord that changes anything in the product roadmap.”

Cordia may resolve:

```text
Need:
Discord messages
+
Notion roadmap
+
comparison
```

Existing capabilities:

```text
discord.read_channel
notion.read_database
compare_changes
```

Cordia can create:

```text
ROADMAP IMPACT

3 engineering updates detected

1 affects roadmap

Authentication API delayed
→ affects Beta Launch

[Review]
```

That new window is generated from reusable capabilities rather than requiring a developer to build a new standalone integration experience.

---

# 6. Capability Hierarchy

The correct abstraction is:

```text
Connector
→ Tool
→ Script
→ Skill
→ Window / action / automation
```

## Connector

Provides access to a system.

Examples:

- Google Drive
- Discord
- Notion
- Mercury
- Claude Code
- Brave Search
- Hostinger
- GitHub
- CordiaCode

## Tool

One primitive operation.

Examples:

```text
drive.list_files
drive.read_file
discord.read_messages
discord.send_message
mercury.list_transactions
brave.search
hostinger.deploy_preview
```

## Script

A deterministic sequence of tools.

Example:

```text
collect_weekly_project_context

1. read Drive project folder
2. read Discord project channel
3. read Notion project page
4. normalize data
5. return context object
```

## Skill

A human-level capability exposed to Cordia.

Examples:

```text
Prepare weekly project review
Compare sources
Summarize research
Prepare client update
Review financial activity
Deploy preview
```

The agent decides **what** is needed.

The skill defines the meaningful capability.

Scripts/tools determine **how** it is executed.

---

# 7. Do Not Make Every Button a Skill

Bad skill definitions:

```text
click_file
open_folder
press_download
click_search_box
```

Good skill definitions:

```text
find_project_documents
summarize_research
compare_versions
prepare_client_update
publish_preview
review_recent_transactions
```

Low-level interactions live below the skill layer.

Example:

```text
SKILL
“Prepare a client update”
        ↓
SCRIPT / TOOL CHAIN
read Discord project channel
read latest Drive files
read Notion project status
summarize changes
draft update
        ↓
PERMISSION CHECK
sending message = ASK
        ↓
Cordia shows preview
```

---

# 8. Skills Should Be Declarative and Composable

Potential skill manifest:

```yaml
id: research.compare_sources

name: Compare Sources

description: >
  Compare information from multiple connected sources
  and surface disagreements or missing evidence.

inputs:
  - sources
  - question

requires:
  connectors:
    - drive
    - brave

permissions:
  - drive.read
  - web.search

execution:
  type: script
  entrypoint: compare_sources.py

outputs:
  type: comparison_report

recommended_window:
  renderer: comparison
```

Long-term, adding a capability should approach:

```text
add skill implementation
register manifest
Cordia can now use it
```

rather than rebuilding the frontend.

---

# 9. Plugins May Disappear as a User-Facing Concept

Users probably do not care about distinctions such as:

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

## Connected

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
Read files              Allow
Send messages           Ask
Execute code            Allow
Deploy                   Ask
Move money               Never
```

The implementation detail can be hidden behind progressive disclosure.

---

# 10. Context Should Be Automatic

Instead of a large technical “Context” configuration screen, Cordia should show something like:

```text
CORDIA CURRENTLY KNOWS FROM

Drive                    142 files
Discord                  3 channels
Notion                   18 pages
Mercury                  90 days
Surveyor                 profile active
Workspace history        27 runs
```

The user can inspect or disable any source.

Context should be an inspection/control surface rather than a setup burden.

---

# 11. Permissions Are About the Cordia Agent

A correction to early UI concepts:

Permissions are **not** primarily about different human users and roles.

They are about what the Cordia agent itself may do in the user’s workspace.

The desired UI model is:

## Cordia can

```text
✓ Read project files
✓ Search the web
✓ Analyze financial records
✓ Execute code
✓ Update Notion pages
```

## Cordia must ask before

```text
? Sending messages
? Publishing code
? Deleting files
? Modifying financial records
? Deploying production
```

## Cordia cannot

```text
✕ Transfer money
✕ Change account security
✕ Add administrators
```

Use:

```text
ALLOW
ASK
DENY
```

This is both a UI model and a runtime enforcement model.

---

# 12. Permission Requirements Belong to Skills/Tools

A skill can declare required permissions.

Example:

```json
{
  "skill": "deploy_preview",
  "requires": [
    "code.read",
    "code.execute",
    "hostinger.preview.deploy"
  ]
}
```

Cordia can run it automatically if all requirements are `ALLOW`.

Production deployment may require:

```text
hostinger.production.deploy = ASK
```

The runtime pauses:

```text
Production deployment requires your approval.

Deploy build cda-82f1 to cordia-app.com?

Cancel     Deploy
```

This is the intended human-in-the-loop model without requiring the user to understand orchestration graphs.

---

# 13. Cordia Agent Placement in the Workspace

The assistant should be on the **left side of the workspace from top to bottom**.

It should not feel like a separate panel from another product.

It is part of the workspace itself.

Target structure:

```text
┌───────────────────┬─────────────────────────────────────────────┐
│                   │                                             │
│ Cordia Agent      │          Visual Workspace                   │
│                   │                                             │
│ full-height chat  │ Drive      Discord      Claude Code         │
│                   │                                             │
│ config chats      │ Hostinger  Mercury      Notion              │
│                   │                                             │
│ approvals         │ Brave      CordiaCode   Derived Views       │
│                   │                                             │
├───────────────────┴─────────────────────────────────────────────┤
│ Connected │ Skills │ Access │ Context │ Automations │ Activity   │
└─────────────────────────────────────────────────────────────────┘
```

---

# 14. Build by Conversation

The user should rarely need to manually configure technical infrastructure.

Example:

```text
User:
Connect Discord, but only monitor the research and announcements channels.

Cordia:
I found Cordia HQ. Research and announcements require message read access only. Connect it?

[Connect Discord]
```

Another:

```text
User:
Let Claude Code work on this project but don’t let it deploy.

Cordia:
I’ll allow project read/write and code execution. Deployment remains blocked.

[Apply]
```

The permissions UI still exists, but primarily for inspection and overrides.

---

# 15. Workspace Is Both Builder and Runtime

A central product decision:

> Building and using the workspace are the same mode.

Do not create a strong separation between “workspace builder” and “workspace runtime.”

The workspace evolves as the user uses it.

The Cordia agent remains embedded and continues changing the workspace when requested.

---

# 16. Canonical Workspace State

The workspace should have one canonical state object.

Conceptually:

```text
Workspace
├── windows
├── connectors
├── skills
├── agents
├── permissions
├── context
├── automations
├── mutations
├── execution state
├── provenance
└── desktop/local capability status
```

Both user customization and Cordia-agent customization should mutate the same state.

Do not maintain separate “AI layout state” and “user layout state.”

---

# 17. Mutations

Every meaningful workspace change should be recorded.

Conceptual fields:

```text
actor
operation
target
target_id
summary
provenance
autonomy
timestamp
```

This enables:

- undo
- audit
- debugging
- explanation
- trust
- future durable state

Example:

```text
User:
“Make Drive larger and move Discord below it.”

→ update Rect
→ record Mutation(actor=USER)
→ UI animates window positions
```

Or:

```text
User:
“Add my recent Drive files.”

Cordia:
“I’ll add your recent Drive files. That only needs Drive read access.”

→ add ConnectorBinding
→ add Window
→ record Mutation(actor=AGENT)
→ frontend updates immediately
```

---

# 18. Connector Lifecycle

Recommended states:

```text
PROPOSED
IN_PROGRESS
LIVE
FAILED
DECLINED
NEEDS_HANDOFF
```

Example proposed state:

```text
Google Drive

Suggested because:
“You said you go to the source before trusting recollection.”

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

1. Open Hostinger
2. Sign in
3. Click Generate API Key when I stop
4. I will finish setup
```

A connector failure should not break the entire workspace.

---

# 19. Surveyor → Workspace Markdown Artifact Pivot

The next major idea was to preserve Surveyor understanding in human-readable markdown artifacts.

The core files are:

```text
operator.md
connectors.md
intent-misses.md
        ↓
fde-tasks.md
permissions.md
workspace-plan.md
```

They are not just documentation. They are operational context used to build and run the personal FDE.

---

# 20. operator.md

`operator.md` answers:

> Who is this person as an operator?

It may contain:

- domain
- work type
- industry context
- goals
- thinking style
- visual/verbal preference
- graph preference
- role tendency
- reasoning tendencies
- correction style
- risk boundaries
- delegation comfort
- preferred human checkpoints
- evidence from Surveyor
- confidence

It should remain inspectable and editable.

---

# 21. connectors.md

`connectors.md` answers:

> What systems does this person already use, and what systems should Cordia consider connecting?

Potential systems include:

- Google Drive
- Discord
- Notion
- Claude Code
- Brave Search
- Hostinger
- Mercury
- Gmail
- Calendar
- GitHub
- CordiaCode
- local repo
- local filesystem
- terminal
- local scripts

For each connector, preserve:

- why it was inferred
- evidence from Surveyor
- whether user confirmed it
- setup strategy
- required access/scopes
- proposed views
- possible skills
- status

---

# 22. fde-tasks.md Should Be the Compiled Mission Brief

The idea was refined further:

`operator.md` and `connectors.md` should **mold together into `fde-tasks.md`**, but should not disappear.

The correct model is:

```text
operator.md + connectors.md + intent-misses.md + workspace goals
        ↓
compiled into
fde-tasks.md
```

`fde-tasks.md` is not just a task list.

It is:

> **The living mission brief for the personal FDE.**

It should describe:

1. who the operator is
2. what they are trying to do
3. what tools/connectors they already use
4. what Cordia is allowed to do
5. where Cordia has previously missed intent
6. what tasks should become windows, skills, scripts, automations, or approvals

Example reasoning:

```text
Operator prefers visual system maps
+
Uses Google Drive, Notion, Discord, Claude Code
+
Wants to build Cordia faster
+
Often notices when AI gives generic architecture instead of executable code
        ↓
FDE task:
“Maintain implementation-ready Cordia build plan with evidence,
repo context, concrete file paths, and no vague framework answers.”
```

---

# 23. fde-tasks.md Is Not the Entire System Prompt

Important refinement:

`fde-tasks.md` should be workspace-specific system context, not the entire global agent prompt.

Runtime layering:

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

This keeps global behavior separate from personal behavior.

---

# 24. Intent-Miss Loop

One of the strongest concepts in the pivot is a looping memory of missed intent.

When Cordia misses the user’s intention, the correction should become structured memory rather than disappearing after regeneration.

Example:

```md
## Intent Miss: 2026-08-12

User asked:
“Give me the actual code, not another framework.”

Cordia did:
Returned architecture guidance and partial pseudocode.

Miss type:
- too abstract
- not implementation-ready
- ignored requested specificity

Correction:
When user asks for code, provide complete runnable files or clearly state what cannot be completed.

Effect on FDE tasks:
Increase preference for concrete implementation over conceptual framing during build sessions.
```

Over time, Cordia can learn operating rules such as:

```text
This user does not want generic SaaS advice.
This user wants concrete build steps, visible UI, files, code paths, and implementation-ready architecture.
```

---

# 25. Avoid Overengineering Numerical Scoring Initially

A hidden numerical scoring system may eventually help, but it should not become the center of the MVP.

Start with simple categorical weights:

```yaml
preferences:
  implementation_specificity: high
  conceptual_explanation: medium
  visual_system_mapping: high
  tolerance_for_vague_answers: low
  autonomy_comfort: medium
  approval_required_for_external_actions: high
```

Later this can evolve to:

```yaml
implementation_specificity:
  value: 0.88
  confidence: 0.74
  evidence:
    - “User repeatedly asked for complete code rather than framework.”
    - “User corrected assistant for being too abstract.”
```

For MVP:

```text
low / medium / high
+
evidence
+
last updated
```

is enough.

---

# 26. Raw Memory vs Compiled Memory

Recommended distinction:

```text
Raw memory:
intent-misses.md
survey-transcript.md
connector-events.md

Compiled memory:
operator.md
connectors.md
fde-tasks.md
workspace-plan.md
permissions.md
```

Cordia should reason primarily from compiled files and consult raw history when it needs evidence.

`fde-tasks.md` should remain concise and operational rather than becoming a giant memory dump.

---

# 27. Full Survey → Workspace Pipeline

Corrected conceptual pipeline:

```text
Surveyor conversation
        ↓
operator.md
        ↓
connector discovery / user confirmation
        ↓
connectors.md
        ↓
workspace goals
        ↓
fde-tasks.md
        ↓
permissions.md
        ↓
workspace-plan.md
        ↓
assessment view
        ↓
workspace builder/runtime
        ↓
real work
        ↓
intent missed?
        ↓
intent-misses.md
        ↓
recompile fde-tasks.md
```

The Surveyor does not directly throw a UI together. It generates evidence and source artifacts that Cordia compiles into the mission and workspace.

---

# 28. MCP Architecture Correction

A later discussion refined the MCP mental model.

The initial thought was that the MCP server might be “the dashboard” and the Cordia agent the client.

The corrected model is:

```text
Dashboard / Workspace UI = visual interface for the human
Cordia Agent = reasoning client/orchestrator
Cordia MCP Server = unified capability gateway
Connectors/APIs/apps = external systems behind the gateway
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

Execution loop:

```text
User
  ↓
Dashboard UI
  ↓
Cordia Agent
  ↓
MCP Server
  ↓
Connector/API/local tool
  ↓
MCP Server
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

# 29. One Connection Through Cordia MCP

The agent should not separately understand every provider’s authentication/runtime mechanics.

Instead:

```text
Every connector becomes a capability exposed through the Cordia MCP server.
The Cordia agent only needs to talk to the Cordia MCP server.
The MCP server handles the actual app/API/browser/local bridge behind it.
```

The agent sees typed capabilities:

```text
drive.search_files
discord.read_channel
hostinger.deploy_preview
mercury.list_transactions
brave.search
claude_code.run_task
```

The gateway decides whether the implementation path is:

- API
- curl
- OAuth
- API key
- Lightpanda
- CLI
- local script
- local MCP server
- desktop local bridge

---

# 30. Lightpanda / Browser Setup Pivot

A major later idea is to use Lightpanda as an agent browser to remove setup hops.

Key product insight:

> Most people do not know how to get an API key.

Cordia should not tell them to find developer settings and copy credentials manually if it can guide the setup.

Correct distinction:

```text
Lightpanda / browser agent = setup assistant
curl/API/MCP = durable runtime
Cordia agent = orchestration client
Cordia MCP server = capability gateway
```

Browser automation should primarily turn a human-only setup path into a durable connector.

After setup, direct API/curl/MCP should be preferred whenever possible.

---

# 31. Guided API-Key Setup

Target experience:

```text
User:
“Connect Hostinger.”

Cordia:
“I can set that up. I’ll open a secure browser session and walk you to the API token page. You only need to sign in and click Generate when I stop.”

[Start secure setup]
```

Flow:

```text
Cordia Browser Setup
        ↓
Open Hostinger
        ↓
Navigate login
        ↓
Cordia may already know the user’s email
        ↓
User manually enters password / 2FA
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

The user should not have to:

```text
Google API docs
find settings
enable developer mode
find API page
generate token
copy token
return to Cordia
paste token
choose scopes
test connection
debug failure
```

Cordia removes those hops.

---

# 32. Password Boundary

Do **not** design the system so the user gives the password directly to the LLM/agent.

Better model:

```text
Cordia can prefill email if approved.
User types password directly into the secure browser.
User completes 2FA directly.
Cordia cannot read the password field value.
Cordia cannot store the password.
Cordia only continues after authentication succeeds.
```

The agent may:

- navigate
- explain
- click safe setup pages
- pause

The agent may not:

- read password values
- export passwords
- retain passwords

---

# 33. API Key Secret Boundary

The API key should not be fed back to the LLM as normal text.

Preferred flow:

```text
API token appears in browser
        ↓
secure setup capture detects the token
        ↓
token goes directly to encrypted secret vault
        ↓
agent receives only status + secret reference
```

Example agent-visible handle:

```json
{
  "secret_ref": "secret_hostinger_api_key_7f31",
  "connector_id": "hostinger",
  "status": "validated"
}
```

The agent should never see:

```text
hst_live_abc123...
```

Future runtime:

```text
Cordia Agent
   ↓ calls typed MCP tool
hostinger.deploy_preview(...)
   ↓
Cordia MCP Server resolves secret_ref internally
   ↓
Hostinger API
```

---

# 34. Enclosed Browser Environment

The guided setup environment should have three boundaries.

## Browser sandbox

```text
ephemeral cookies
ephemeral profile
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

## Tool boundary

The agent should call typed capabilities through MCP rather than arbitrary token-bearing commands.

Good:

```text
hostinger.deploy_preview(site_id)
```

Bad:

```text
curl arbitrary internet URL using unrestricted token access
```

---

# 35. Connector Manifests Need Setup Strategy

Each connector should encode both setup and durable runtime strategy.

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

This allows Cordia to know:

```text
This connector is configured through guided browser setup.
After setup, durable execution uses direct API calls.
```

---

# 36. Browser for Setup, curl/API for Runtime

Use Lightpanda/browser automation for:

- login flows
- API-key creation flows
- OAuth-ish setup pages
- sites without clean APIs
- one-time connector setup
- workflow discovery
- user-guided browser tasks
- fallback when a direct API path does not exist

Use direct API / curl / MCP for:

- normal connector runtime
- repeatable actions
- status checks
- file reads
- message reads
- deploy calls
- search calls
- data sync
- automations

Do not turn Cordia into a brittle browser automation system when a durable API path exists.

---

# 37. Web App vs Desktop App Pivot

Another important correction:

The desktop app is **not installed in the middle of workspace building**.

The user builds the workspace first in the Cordia web application.

The web app is used to:

```text
sign up
complete Surveyor
view assessment
build first workspace
connect cloud applications
save workspace
choose Install Cordia Desktop
```

Only then does the user run `install.ps1`.

The desktop app is the installed form of the workspace the user already built.

---

# 38. install.ps1 Correct Position

Correct lifecycle:

```text
Cordia web app
  → user completes Surveyor
  → user views assessment
  → user builds workspace in browser
  → workspace becomes a saved Cordia workspace
  → user chooses “Install on desktop”
  → install.ps1 installs the Cordia Desktop App
  → user signs in
  → desktop app loads the same workspace locally
  → Cordia agent remains embedded
  → user keeps modifying the workspace from desktop
```

`install.ps1` is therefore a **deployment/export/install step**, not part of initial workspace generation.

---

# 39. Desktop Experience

The Cordia Desktop App should:

- use the same account/email identity
- load the same cloud-saved workspace
- retain the same Cordia agent
- preserve the same windows/configuration
- keep allowing workspace modification
- add access to local capabilities

The product story is:

> **Take the workspace I built in Cordia and install it as my local AI operating environment.**

---

# 40. Desktop Local Bridge

Once the desktop app is installed, local capabilities can appear.

Examples:

- Claude Code
- local repo
- local filesystem
- PowerShell
- Python scripts
- Docker
- VS Code project
- terminal commands
- local MCP servers
- private dev environment

Example before desktop install:

```text
Cloud:
✓ Drive
✓ Discord
✓ Notion
✓ Brave Search
✓ Hostinger
✓ Mercury
```

Example after desktop install:

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

The local bridge still obeys ALLOW / ASK / DENY permissions.

---

# 41. Desktop Install Flow

Conceptual flow:

```text
User clicks “Install Cordia Desktop”
        ↓
Download/run install.ps1
        ↓
Install Cordia Desktop App
        ↓
User opens app
        ↓
User signs in with same email
        ↓
Desktop pulls saved workspace
        ↓
Desktop registers local device
        ↓
Enable local bridge
        ↓
Discover local capabilities
        ↓
Sync capability availability to workspace
        ↓
Same workspace becomes local-capable
```

`install.ps1` should not blindly grant full machine control.

Local access should be explicit and least-privilege.

---

# 42. Full Corrected Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│                         CORDIA CLOUD                               │
└────────────────────────────────────────────────────────────────────┘

        ┌────────────────────┐
        │ User Account/Auth  │
        └─────────┬──────────┘
                  │
                  ▼
        ┌────────────────────┐
        │ Surveyor Agent     │
        │ Natural Chat       │
        └─────────┬──────────┘
                  │
                  ▼
┌───────────────────────────────────────┐
│ Source Markdown Artifacts             │
│                                       │
│ operator.md                           │
│ connectors.md                         │
│ intent-misses.md                      │
└──────────────────┬────────────────────┘
                   │ compile
                   ▼
┌───────────────────────────────────────┐
│ Runtime Markdown Artifacts            │
│                                       │
│ fde-tasks.md                          │
│ permissions.md                        │
│ workspace-plan.md                     │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ Survey Assessment View                │
│                                       │
│ What Cordia understands               │
│ No score / no pass-fail               │
└──────────────────┬────────────────────┘
                   │ approve/refine
                   ▼
┌───────────────────────────────────────┐
│ Workspace Builder / Workspace Runtime │
│                                       │
│ Left: Cordia Agent                    │
│ Right: Visual Workspace               │
│ Bottom: Inspection Dock               │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ Canonical Workspace State             │
│                                       │
│ windows                               │
│ connectors                            │
│ skills                                │
│ permissions                           │
│ context                               │
│ automations                           │
│ mutations                             │
│ provenance                            │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ Cordia Agent Runtime                  │
│                                       │
│ Reads fde-tasks.md                    │
│ Reads permissions.md                  │
│ Reads workspace state                 │
│ Chooses skills                        │
│ Asks approval when required           │
└──────────────────┬────────────────────┘
                   │ calls
                   ▼
┌───────────────────────────────────────┐
│ Cordia MCP Server                     │
│                                       │
│ Unified capability gateway            │
│ Tool registry                         │
│ Connector routing                     │
│ Permission enforcement                │
│ Secret refs                           │
│ Audit/provenance                      │
└──────────────────┬────────────────────┘
                   │
      ┌────────────┼──────────────────────────┐
      │            │                          │
      ▼            ▼                          ▼
┌──────────┐ ┌─────────────────┐    ┌──────────────────┐
│ Cloud    │ │ Guided Browser  │    │ Desktop Local    │
│ APIs     │ │ Setup Assistant │    │ Bridge           │
└────┬─────┘ └────────┬────────┘    └────────┬─────────┘
     │                │                      │
     ▼                ▼                      ▼
Drive           Lightpanda              Claude Code
Discord         API-key setup           Local files
Notion          OAuth-ish setup         Local repo
Brave           Human login/2FA         Terminal
Hostinger       Secret capture          PowerShell
Mercury         Vault write             Python scripts
GitHub                                  Docker
CordiaCode                              Local MCP servers


After workspace is saved:

User clicks “Install Cordia Desktop”
        ↓
Download/run install.ps1
        ↓
Install Cordia Desktop App
        ↓
User signs in with same email
        ↓
Desktop app pulls saved workspace
        ↓
Register local device
        ↓
Enable local bridge
        ↓
Same workspace runs locally with Cordia agent embedded
```

---

# 43. Core Product Loop After Deployment

The long-term FDE loop is:

```text
PERSON
  │
  │ natural language
  ▼
CORDIA FDE AGENT
  │
  │ understands need
  ▼
CAPABILITY RESOLUTION
  │
  ├── known skill
  └── new composition
          ↓
    permission check
      /          \
  allowed        ask
      \          /
          ↓
MCP / script / API / local tool
          ↓
canonical workspace state
          ↓
workspace changes
          ↓
human sees result
          ↓
feedback / intent miss
          ↺
```

---

# 44. MVP Simplicity Principle

The strongest architecture is not the one with the most agentic machinery.

It is the one that proves:

```text
Surveyor understands something useful
        ↓
that understanding becomes inspectable artifacts
        ↓
artifacts compile into FDE tasks
        ↓
FDE tasks generate a workspace
        ↓
Cordia can change the workspace through chat
        ↓
one connector can actually be configured
        ↓
one real skill can execute through the MCP gateway
        ↓
workspace visibly updates
        ↓
user can later install the same workspace on desktop
```

Do not start by supporting every connector.

Start with one cloud connector and one local capability.

---

# 45. Product Thesis Emerging From This Pivot

The strongest summary of the current direction is:

```text
Surveyor creates understanding.
operator.md preserves who the user is.
connectors.md preserves what systems they use.
intent-misses.md preserves how AI has failed to understand them.
fde-tasks.md compiles what the personal FDE should actually do.
workspace-plan.md compiles what should appear visually.
permissions.md determines Cordia’s autonomy.
The workspace UI renders canonical workspace state.
The Cordia Agent reasons over that state.
The Cordia MCP Server exposes all capabilities behind one gateway.
Lightpanda removes human setup hops.
Direct API/curl/MCP becomes the durable runtime.
The web app creates and saves the workspace.
install.ps1 installs that already-created workspace as a desktop application.
The desktop app adds local capabilities while keeping the same agent and workspace.
Intent misses continuously improve the FDE mission.
```

The underlying product promise is:

> **The user does not need to understand APIs, MCP, agent graphs, or technical integration to get an API-powered personal AI workspace.**

And the deeper Cordia thesis remains:

> **Cordia translates human intention into the technical setup required to make AI useful.**
