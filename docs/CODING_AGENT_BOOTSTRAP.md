# Cordia Coding Agent Bootstrap

You are working on the private GitHub repository:

`ItzJLaugh/Cordia`

Before writing code:

1. Inspect the repository.
2. Read `docs/CORDIA_BUILD_CONTEXT.md` in full.
3. Read `docs/WORKSPACE_FDE_PIVOT_CONTEXT.md` in full.
4. Read `docs/TODO_CORDIA_VERTICAL_SLICE.md` in full.
5. Read `docs/ALIDORA_INTEGRATION_CHARTER.md` in full before touching dashboard, graph, workflow, agent-composition, or advanced-runtime code.
6. Identify existing implementations for:
   - Surveyor
   - Surveyor assessment/profile
   - markdown artifacts
   - certifications
   - courses
   - workspace/workspace builder
   - canonical workspace state
   - connectors
   - MCP/tool/skill infrastructure
   - permissions/scopes logic
   - agent/runtime logic
   - browser-assisted connector setup
   - desktop install
   - local bridge
   - current frontend design system
7. Do not create a parallel architecture before understanding what already exists.
8. Explain how the current code maps to the canonical product model.
9. Explicitly identify:
   - what is already implemented
   - what is partially implemented
   - what needs refactoring
   - what is missing
10. Preserve simplicity. Cordia is an agentic Forward Deployed Engineer for the individual. Alidora — Agentic System Builder by Cordia is the explicit advanced module for company agentic systems; it must share Cordia's contracts rather than creating a generic parallel platform.
11. Do not begin a broad rewrite until this analysis is complete.

---

# Current Product Direction

Cordia is a personal agentic Forward Deployed Engineer.

The user completes Surveyor, views a non-scored assessment, builds a workspace in the Cordia web app, connects tools/apps/APIs with Cordia’s help, then can install that saved workspace as a local Cordia Desktop App using `install.ps1`.

The desktop app is **not** part of the initial build process. It is the local deployment of the workspace after the workspace is already created.

Core architecture:

```text
Surveyor
  → operator.md / connectors.md / intent-misses.md
  → fde-tasks.md / permissions.md / workspace-plan.md
  → assessment
  → workspace builder/runtime
  → canonical workspace state
  → Cordia agent runtime
  → Cordia MCP server
  → cloud APIs / guided browser setup / desktop local bridge
  → live workspace
```

---

# Markdown Artifact Intent

Treat these as distinct source/runtime artifacts:

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
    What Cordia can do, must ask before doing, or cannot do.

workspace-plan.md
    What visual workspace Cordia should build.
```

The key compile relationship is:

```text
operator.md + connectors.md + intent-misses.md + current workspace goals
        ↓
compiled into
fde-tasks.md
```

`fde-tasks.md` is not the entire global system prompt. It is workspace-specific mission context layered under global Cordia behavior and safety rules.

---

# Workspace UX

Workspace windows are agent-built artifacts. Default to a Cordia-native interactive DashView assembled from connectors, skills, artifacts, permissions, and context. A LiveView is allowed only when the connector supports it and the user explicitly enables it. A DerivedView combines multiple sources. Preserve each artifact's purpose, sources, provenance, view mode, and action permission requirements.

The intended workspace experience is conversational:

- Cordia agent occupies the left side of the workspace from top to bottom.
- User communicates with Cordia to configure the workspace.
- The main workspace visually shows real Cordia-native views of connected systems or derived task surfaces.
- Connectors expose capabilities.
- Tools are primitive operations.
- Scripts are deterministic procedures.
- Skills represent meaningful human-level capabilities.
- MCP/APIs/CLI/local tools are implementation details underneath that capability model.
- Permissions describe what the Cordia agent may `ALLOW`, must `ASK` before, or must `DENY`.
- The user should rarely need to manually configure technical infrastructure.
- Building and using the workspace are the same mode.

Do not turn the product into a node-graph editor unless a technical/advanced view specifically needs one.

Alidora is that advanced view. Keep it a named Cordia module/tab for users who need agent-system composition, graph inspection, runs, and approvals. The standard Cordia workspace remains chat-first with connector-native and derived task surfaces.

For any parallel implementation or external PR, review each component against current contracts and classify it as adopt, adapt, compose, or reject. Never preserve duplicate ownership of workspace state, registries, permissions, execution, secrets, or outcomes.

When implementing an approved Alidora plan, work task-by-task in an isolated branch/worktree. Each task requires its own focused tests, an independent validation review of the actual diff, and a recorded review result before the next task begins. Do not batch-merge an external dashboard/runtime stack without these gates.

---

# MCP Role

Important correction:

The MCP server is not the dashboard.

```text
Dashboard / Workspace UI = human-facing interface
Cordia Agent = reasoning client/orchestrator
Cordia MCP Server = unified capability gateway
Connectors/APIs/apps/local tools = systems behind the gateway
```

The agent should primarily talk to the Cordia MCP server rather than independently managing every provider implementation.

The MCP server/gateway hides whether a capability is implemented using:

- OAuth
- API key
- REST API
- curl
- Lightpanda
- CLI
- local script
- local MCP server
- desktop bridge

---

# Guided Connector Setup

Use Lightpanda/browser automation as a setup assistant for API-key or web-only setup flows.

Use direct API/curl/MCP calls for durable runtime after setup whenever possible.

Desired flow:

```text
User: Connect Hostinger.
        ↓
Cordia opens secure guided setup.
        ↓
Agent navigates to login/API settings.
        ↓
User enters password and 2FA directly.
        ↓
Agent pauses at Generate API Key.
        ↓
User clicks Generate.
        ↓
Secret is captured directly into encrypted vault.
        ↓
Agent receives secret_ref/status, not raw key.
        ↓
Cordia validates with direct API/curl.
        ↓
Connector becomes live.
```

Credential boundary:

- Agent may navigate.
- Agent may explain.
- Agent may fill known email if explicitly allowed.
- User enters password/2FA directly.
- Agent must not read/store password values.
- Raw API keys should not enter normal LLM prompt context.

---

# Workspace Windows

Windows are Cordia-native representations of connectors or derived task views, not iframe embeds of entire external websites.

Example connector-native windows:

- Drive recent/project files
- Discord selected channels
- Notion roadmap/tasks
- Mercury financial overview
- Hostinger deploy/status
- Claude Code local project status

Example derived window:

```text
ROADMAP IMPACT

3 engineering updates detected
1 affects roadmap

Authentication API delayed
→ affects Beta Launch
```

Derived windows may combine multiple connectors and skills.

---

# Permissions

Permissions are what Cordia is allowed to do, not user roles.

Use:

```text
ALLOW
ASK
DENY
```

Examples:

```text
Read project files        ALLOW
Search web                ALLOW
Execute code              ALLOW
Send messages             ASK
Deploy production         ASK
Delete files              ASK
Transfer money            DENY
Change account security   DENY
```

Permissions must be enforced before execution, not only shown in UI.

---

# Desktop App

The desktop install is downstream of a completed/saved web workspace.

Correct flow:

```text
User builds workspace in Cordia Web
        ↓
Workspace is saved
        ↓
User chooses Install Cordia Desktop
        ↓
Download/run install.ps1
        ↓
Cordia Desktop App installs
        ↓
User signs in with same email
        ↓
Desktop app loads same workspace
        ↓
Local bridge registers local capabilities
        ↓
Same Cordia agent remains embedded
        ↓
User continues modifying/using workspace locally
```

The desktop app should add local capabilities such as:

- Claude Code
- local repo
- local filesystem
- PowerShell
- Python scripts
- Docker
- VS Code project
- terminal
- local MCP servers

Do not treat `install.ps1` as a prerequisite for building the initial workspace.

---

# Intent-Miss Memory

When Cordia misses the user’s intent, do not merely regenerate.

Record a structured intent-miss event and use it to refine future behavior and `fde-tasks.md`.

For MVP, prefer simple inspectable categories such as:

```text
low / medium / high
+
evidence
+
last updated
```

over premature complex numerical models.

---

# First Required Analysis

After inspecting the repository, give me:

1. a current-state architecture map
2. the exact path from Surveyor → profile/artifacts → assessment → workspace proposal → connector provisioning → live workspace
3. the current data contracts involved
4. the current MCP/tool/connector architecture
5. the current permission model
6. the current desktop/local-runtime situation
7. gaps between implementation and `docs/CORDIA_BUILD_CONTEXT.md`
8. gaps between implementation and `docs/WORKSPACE_FDE_PIVOT_CONTEXT.md`
9. the smallest sensible implementation sequence for completing the real vertical slice

Do not write code until this mapping is complete unless explicitly instructed otherwise.
