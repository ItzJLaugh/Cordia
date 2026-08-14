# Cordia Electron Desktop MVP Design

## Goal

Install the already-saved Cordia workspace as a Windows desktop application
without creating a second workspace or granting uncontrolled access to the
machine.

## Scope

The first desktop MVP is intentionally narrow:

- Electron is the Windows shell.
- The renderer loads the same Cordia web workspace and signs in through the
  existing Cordia account flow.
- The cloud workspace remains authoritative. Desktop does not create an
  alternate local workspace store.
- A preload bridge exposes only desktop metadata and a read-only local
  repository discovery capability.
- Local repository discovery is explicit: the user selects a directory through
  a native folder chooser. The bridge returns safe metadata only (path label,
  Git root, branch if available); it never uploads file contents.
- The local capability is represented as a typed capability through the same
  Cordia capability registry and permission decision model. Read is `ALLOW`
  only after explicit local selection; write, shell, package install, push, and
  deployment remain unavailable in this MVP.
- `install.ps1` installs the Electron desktop package only after a workspace is
  already saved in the web product.

## Non-goals

- No arbitrary PowerShell, terminal, filesystem, Docker, Claude Code, or MCP
  execution.
- No local-first synchronization, background filesystem indexing, or hidden
  folder scanning.
- No new cloud authentication system, Tailscale enrollment integration, or
  production deployment changes.
- No claim that a desktop app is live until a signed/packaged Windows build has
  been installed and exercised.

## Architecture

```text
Cordia Cloud workspace (authoritative)
        |
Electron BrowserWindow
        |
preload contextBridge (narrow, typed API)
        |
Electron main process
        |
native directory picker -> selected Git repository metadata
```

The renderer has no Node.js access. Context isolation stays enabled and remote
navigation is restricted to the configured Cordia cloud origin plus local
development origins. The main process validates every IPC request and never
executes shell commands supplied by the renderer.

## Data and permissions

The desktop bridge returns a record shaped as:

```json
{
  "kind": "local_repository",
  "id": "local-repo:<opaque-id>",
  "label": "repository-folder",
  "path_label": "C:\\…\\repository-folder",
  "git_root": true,
  "branch": "main"
}
```

The absolute path is local-only and is never included in cloud workspace
mutations or prompts. The renderer may send only the opaque id and safe label
to the cloud workspace as context provenance. The desktop app stores selected
path mappings locally in Electron user data so a restarted desktop session can
reconfirm availability without rediscovery.

The new gateway capability is `desktop.local_repository.describe`:

- `ALLOW` only when the desktop bridge reports a selected repository.
- `ASK` for local write or shell-style actions.
- `DENY` for unregistered actions and credential exposure.

## Error handling

- If Electron cannot reach Cordia cloud, show the regular cloud connection
  failure; do not use stale local state as an authoritative workspace.
- Canceling the directory picker is a normal no-op.
- A chosen non-Git folder returns a safe validation error and is not registered.
- A repository removed after selection reports unavailable and does not delete
  its cloud context automatically.
- IPC schema failures return bounded safe messages only.

## Verification

1. Unit-test preload API shape and main-process path validation with a temporary
   Git directory fixture.
2. Unit-test that arbitrary path, shell, and write IPC channels are absent.
3. Run Electron packaging/build checks on Windows.
4. Install with `install.ps1`, sign into the same account, and verify the
   saved workspace appears unchanged.
5. Select a Git repository, confirm only safe metadata appears, and confirm the
   associated read capability is available.
6. Confirm no local write/shell operation can be invoked.
