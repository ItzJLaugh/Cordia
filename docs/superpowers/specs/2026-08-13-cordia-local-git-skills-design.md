# Cordia Local Git Skills Design

## Goal

Make Cordia demonstrably useful against a repository the person explicitly
selects, without turning the desktop app into a general terminal or sending
local paths, source code, or Git credentials to Cordia cloud services.

The first skills are deliberately small:

1. **Git status / wait**: inspect repository state and optionally recheck a
   declared repository condition.
2. **Git pull**: show a local preview and require a fresh human approval before
   fetching and fast-forwarding the selected repository.
3. **Git push**: show a local preview and require a fresh human approval before
   pushing the selected branch to its configured upstream.

## Architecture

```text
Cordia cloud workspace (authoritative intent and approval display)
        | safe skill result + opaque repository ID only
Electron preload (fixed named API)
        |
Electron main process (selected-path map; local approval binding)
        |
allow-listed Git adapter (fixed git argv; no shell)
        |
user-selected Git repository
```

The Electron main process owns an in-memory/user-data mapping from the opaque
repository ID to its local path. The renderer, backend, and prompts never
receive that path. The Git adapter uses `spawnFile`/`execFile` with fixed
arguments, never a shell string and never renderer-supplied command arguments.

The cloud backend can display an approval and record the person's decision, but
it does not execute Git. The desktop app binds a decision to an opaque action
descriptor and rechecks it immediately before the local mutation.

## Capability boundaries

| Capability | Local operation | Default decision | Result exposed to cloud |
|---|---|---|---|
| `desktop.git.status` | `git status --porcelain=v1 --branch` | ALLOW after selection | branch, clean/dirty, ahead/behind counts |
| `desktop.git.wait` | repeat status at bounded interval | ALLOW after selection | requested condition and final status |
| `desktop.git.pull` | `git pull --ff-only` | ASK | branch, upstream, preview, completion/error summary |
| `desktop.git.push` | `git push` for configured upstream | ASK | branch, upstream, preview, completion/error summary |

No capability accepts a free-form Git argument, refspec, remote URL, repository
path, commit message, shell command, credential, or environment override.
Unknown desktop Git capability IDs are denied. There is no clone, checkout,
reset, merge, commit, force-push, tag, submodule, config, credential, package,
or deployment capability in this slice.

## Skill behavior

### Git status / wait

`git_status_wait` begins with status. It may return immediately, or wait for one
of three declared conditions: `clean`, `incoming_changes`, or `synchronized`.
It polls at a bounded local interval with a bounded timeout. It does not fetch,
pull, push, or modify the repository while waiting. Timeouts are a normal
result, not an error and not a background task.

### Git pull

`git_pull` first obtains status and validates an upstream. It returns a preview
that says whether the tree is dirty and whether the configured upstream exists.
The person then explicitly approves the exact local action for the repository
and branch. Before calling `git pull --ff-only`, Cordia rechecks that the
selected repository mapping, branch, upstream, and approval nonce still match.
It refuses a dirty working tree, no upstream, non-fast-forward result, expired
approval, declined approval, or changed branch. It never resolves credentials;
Git's existing local credential mechanism remains private to Git.

### Git push

`git_push` uses the same preview and fresh approval model. Its exact local
operation is fixed to `git push` for the current branch's configured upstream;
no force or arbitrary remote/refspec is available. It refuses dirty working
trees, no upstream, expired/declined/mismatched approval, or changed branch.
The Git process result is reduced to a bounded safe completion/error summary.

## Approval model

The desktop generates an opaque pending action ID after preview. The web
workspace may display it through the existing approval UI, but the local action
remains pending until the desktop receives a matching approval decision. A
decision is single-use and expires after five minutes. Decline, cancel,
timeout, changed selected repository, changed branch, or restart invalidates it.

The design intentionally does not trust an arbitrary cloud request as
authorization to mutate a local repository. The Electron app performs the final
action binding and revalidation locally.

## Error handling and privacy

- Selection cancellation is a normal no-op.
- A missing or moved selected repository is unavailable; Cordia does not scan
  for it or remove cloud context automatically.
- Git executable absence and process failure return bounded user-facing errors.
- The adapter emits no source file content, diff, remote URL, absolute path,
  credentials, or raw process environment to renderer/cloud logs.
- Child process output is byte-limited before transformation.
- A failed fetch/pull/push does not retry automatically.

## Verification

1. Unit-test fixed Git argv construction and reject arbitrary operation names.
2. Test local status parsing with clean, dirty, ahead/behind, and no-upstream
   fixtures without reading source content.
3. Test each wait condition and bounded timeout with a fake status provider.
4. Test pull/push require matching, unexpired, single-use approval and reject
   dirty/upstream/branch-change cases before spawning Git.
5. Test the preload exposes only the named Git methods; arbitrary IPC and shell
   APIs remain absent.
6. Exercise a disposable local test repository for status, a non-mutating wait,
   then approval-declined pull/push. Successful network pull/push requires a
   separate disposable remote and explicit user approval during the live test.

## Non-goals

- Cloud-side Git execution or storage of local repository mappings.
- Background watchers, automatic sync, retries, or credential management.
- Arbitrary terminal access, Git CLI passthrough, or direct write operations.
- Force pushes and other history-rewriting operations.
